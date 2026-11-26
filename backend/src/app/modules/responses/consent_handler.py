import hashlib
import json

from sqlalchemy import select, text

from app.core.exceptions import AppError
from app.core.response_handler import ResponseHandler
from app.modules.audit.models import AuditEvent, AuditOutcome
from app.modules.audit.schemas import AuditAction, AuditEventInput
from app.modules.audit.service import record_event
from app.modules.candidates.consent_models import ConsentSource, TalentPoolConsent
from app.modules.responses.consent_policy import policy_text
from app.modules.settings.models import SystemSetting


def grant_values(grant):
    if grant is None:
        return None
    return {
        "id": grant.id,
        "application_id": grant.application_id,
        "source": grant.source.value,
        "policy_ver": grant.policy_ver,
        "consented_at": grant.consented_at.isoformat(),
        "expires_at": grant.expires_at.isoformat(),
        "revoked_at": grant.revoked_at.isoformat() if grant.revoked_at else None,
    }


class TalentPoolResponseHandler(ResponseHandler):
    async def _grant(self, ctx):
        return await self.session.scalar(
            select(TalentPoolConsent)
            .where(
                TalentPoolConsent.candidate_id == ctx.candidate.id,
                TalentPoolConsent.revoked_at.is_(None),
            )
            .execution_options(populate_existing=True)
        )

    async def _evidence(self, grant):
        events = await self.session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.action == "talent_pool.consent_granted",
                AuditEvent.target_type == "application",
                AuditEvent.event_metadata["changes"]["consent_id"].as_integer() == grant.id,
            )
            .order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
        )
        for event in events:
            evidence = event.event_metadata.get("changes", {}).get("after", {})
            if (
                evidence.get("policy_ver") == grant.policy_ver
                and evidence.get("consented_at") == grant.consented_at.isoformat()
                and evidence.get("expires_at") == grant.expires_at.isoformat()
                and isinstance(evidence.get("retention_months"), int)
                and evidence.get("policy_text")
                == policy_text(grant.policy_ver, evidence["retention_months"])
            ):
                return evidence
        raise AppError("Không tải được nội dung chính sách", 503, "consent_policy_unavailable")

    async def view(self, ctx):
        grant = await self._grant(ctx)
        valid = grant is not None and grant.expires_at > ctx.now
        setting = await self.session.get(SystemSetting, "talent_pool_months")
        if setting is None or setting.value is None:
            raise AppError("Thiếu cấu hình thời hạn lưu hồ sơ", 503, "configuration_error")
        months = int(setting.value)
        version = self.settings.talent_pool_policy_version
        if valid:
            evidence = await self._evidence(grant)
            months = evidence["retention_months"]
            version = grant.policy_ver
            display = evidence["policy_text"]
        else:
            display = policy_text(version, months)
        state = dict(grant=grant_values(grant), valid=valid, months=months, policy_ver=version)
        digest = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
        return dict(
            consent_mode="ACKNOWLEDGE" if valid else "GRANT",
            policy_ver=version,
            policy_text=display,
            retention_months=months,
            consent_snapshot=digest,
            consent_expires_at=grant.expires_at if valid else None,
            allowed_actions=["ACCEPTED"] if valid else ["ACCEPTED", "DECLINED"],
        )

    async def apply(self, ctx, payload):
        if not payload.consent_snapshot or (
            payload.action == "ACCEPTED" and not payload.policy_ver
        ):
            raise AppError(
                "Thiếu thông tin chính sách đã hiển thị", 422, "invalid_consent_response"
            )
        view = await self.view(ctx)
        if payload.consent_snapshot != view["consent_snapshot"]:
            code = (
                "policy_changed"
                if payload.policy_ver and payload.policy_ver != view["policy_ver"]
                else "consent_changed"
            )
            raise AppError("Thông tin đồng ý đã thay đổi, vui lòng tải lại", 409, code)
        if payload.action not in view["allowed_actions"]:
            raise AppError("Phản hồi không hợp lệ", 422, "invalid_response_action")
        grant = await self._grant(ctx)
        if payload.action == "ACCEPTED" and payload.policy_ver != view["policy_ver"]:
            raise AppError("Chính sách đã thay đổi, vui lòng tải lại", 409, "policy_changed")
        before = grant_values(grant)
        if payload.action == "DECLINED":
            action = AuditAction.TALENT_POOL_CONSENT_DECLINED
            message = "Đã ghi nhận phản hồi của bạn."
            changes = {"consent_id": grant.id if grant else None}
        elif view["consent_mode"] == "ACKNOWLEDGE":
            action = AuditAction.TALENT_POOL_CONSENT_ACKNOWLEDGED
            message = "Đã ghi nhận. Thời hạn lưu hồ sơ hiện tại được giữ nguyên."
            changes = {"consent_id": grant.id, "acknowledged_policy_ver": grant.policy_ver}
        else:
            expires = await self.session.scalar(
                text(
                    "SELECT ((CAST(:at AS timestamptz) AT TIME ZONE 'Asia/Ho_Chi_Minh')"
                    " + make_interval(months => :months)) AT TIME ZONE 'Asia/Ho_Chi_Minh'"
                ),
                {"at": ctx.now, "months": view["retention_months"]},
            )
            if grant is None:
                grant = TalentPoolConsent(candidate_id=ctx.candidate.id)
                self.session.add(grant)
            grant.application_id = ctx.application.id
            grant.source = ConsentSource.THANK_YOU_LINK
            grant.policy_ver = view["policy_ver"]
            grant.consented_at = ctx.now
            grant.expires_at = expires
            await self.session.flush()
            after = grant_values(grant)
            after.update(policy_text=view["policy_text"], retention_months=view["retention_months"])
            changes = {"consent_id": grant.id, "before": before, "after": after}
            action = AuditAction.TALENT_POOL_CONSENT_GRANTED
            message = "Đã ghi nhận sự đồng ý lưu hồ sơ của bạn."
        await record_event(
            self.session,
            AuditEventInput(
                action=action,
                outcome=AuditOutcome.SUCCESS,
                target_type="application",
                target_id=str(ctx.application.id),
                metadata={"changes": changes},
            ),
        )
        ctx.application.version += 1
        ctx.application.updated_at = ctx.now
        return {"outcome": payload.action, "message": message}
