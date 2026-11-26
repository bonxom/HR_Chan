import React, { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { CheckCircle2, AlertCircle } from 'lucide-react';
import { Modal } from '../../shared/components/ui/Modal';
import { Button } from '../../shared/components/ui/Button';
import { Input } from '../../shared/components/ui/Input';
import { env } from '../../configs/env';
import { useFocusFirstError } from '../jobs/useErrorFocus';
import { listPublicJobs } from '../jobs/publicApi';
import { createSubmission, requestApplicationOtp } from './api';
import { OtpModal } from './OtpModal';
import { TurnstileWidget } from './TurnstileWidget';
import type { ApplicationCreated, OtpIssued, Submission, SubmissionInput } from './types';
import {
  APPLY_FIELD_ORDER,
  mapServerError,
  normalizePhone,
  validateApply,
  validateCvFile,
  type ApplyErrors,
  type ApplyField,
} from './validation';

interface TargetJob {
  id: number;
  title: string;
}

interface ApplyModalProps {
  isOpen: boolean;
  onClose: () => void;
  preselectedJob?: TargetJob | null;
}

type Step = 'FORM' | 'JOB' | 'OTP' | 'DONE';

const FIELD_IDS: Record<ApplyField, string> = {
  fullName: 'apply-full-name',
  email: 'apply-email',
  phone: 'apply-phone',
  file: 'apply-cv-file',
  consent: 'apply-consent',
  captcha: 'apply-captcha',
};

const FIELD_BASE =
  'block w-full text-xs text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-emerald-50 file:px-3 file:py-2 file:text-xs file:font-semibold file:text-emerald-700';

export const ApplyModal: React.FC<ApplyModalProps> = ({ isOpen, onClose, preselectedJob }) => {
  const [step, setStep] = useState<Step>('FORM');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [consent, setConsent] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaReset, setCaptchaReset] = useState(0);
  const [errors, setErrors] = useState<ApplyErrors>({});
  const [general, setGeneral] = useState('');
  const [focusRequest, setFocusRequest] = useState(0);

  // Capability và OTP chỉ nằm trong bộ nhớ; mất khi đóng, quay lại sửa hoặc đổi liên hệ.
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [chosenJobId, setChosenJobId] = useState<number | null>(null);
  const [targetJob, setTargetJob] = useState<TargetJob | null>(null);
  const [otp, setOtp] = useState<OtpIssued | null>(null);
  const [created, setCreated] = useState<ApplicationCreated | null>(null);

  const firstInvalid = APPLY_FIELD_ORDER.find((field) => errors[field]);
  useFocusFirstError(focusRequest, firstInvalid ? FIELD_IDS[firstInvalid] : undefined, 'apply-summary');

  // Mỗi lần đóng/quay lại/đặt lại tăng thế hệ; phản hồi của thế hệ cũ bị bỏ qua hoàn toàn.
  const generation = useRef(0);

  const reset = () => {
    generation.current += 1;
    // Tách khỏi yêu cầu đang bay: trạng thái pending cũ không chặn form mới (callback cũ bị bỏ qua).
    uploadMutation.reset();
    otpMutation.reset();
    setStep('FORM');
    setFullName('');
    setEmail('');
    setPhone('');
    setConsent(false);
    setFile(null);
    setCaptchaToken(null);
    setCaptchaReset((n) => n + 1);
    setErrors({});
    setGeneral('');
    setSubmission(null);
    setChosenJobId(null);
    setTargetJob(null);
    setOtp(null);
    setCreated(null);
  };

  useEffect(() => {
    if (!isOpen) reset();
  }, [isOpen]);

  const close = () => {
    reset();
    onClose();
  };

  const showErrors = (next: ApplyErrors, message = '') => {
    setErrors(next);
    setGeneral(message);
    setFocusRequest((n) => n + 1);
  };

  const consumeCaptcha = () => {
    // Token Turnstile chỉ dùng được một lần.
    setCaptchaToken(null);
    setCaptchaReset((n) => n + 1);
  };

  const otpMutation = useMutation({
    mutationFn: (variables: { sub: Submission; job: TargetJob; gen: number }) =>
      requestApplicationOtp({
        submissionId: variables.sub.submissionId,
        submissionToken: variables.sub.submissionToken,
        jobId: variables.job.id,
      }),
    onSuccess: (issued, variables) => {
      if (variables.gen !== generation.current) return;
      setTargetJob(variables.job);
      setOtp(issued);
      setGeneral('');
      setStep('OTP');
    },
    onError: (error, variables) => {
      if (variables.gen !== generation.current) return;
      // Giữ submission đã tải: người dùng thử gửi mã lại mà không phải tải CV lần nữa.
      setTargetJob(variables.job);
      setStep('JOB');
      setGeneral(mapServerError(error).general ?? mapServerError(error).fields.file ?? 'Không gửi được mã xác thực.');
    },
  });

  const uploadMutation = useMutation({
    mutationFn: ({ input }: { input: SubmissionInput; gen: number }) => createSubmission(input),
    onSuccess: (sub, variables) => {
      if (variables.gen !== generation.current) return;
      consumeCaptcha();
      setSubmission(sub);
      setErrors({});
      setGeneral('');
      if (preselectedJob) otpMutation.mutate({ sub, job: preselectedJob, gen: variables.gen });
      else setStep('JOB');
    },
    onError: (error, variables) => {
      if (variables.gen !== generation.current) return;
      consumeCaptcha();
      const { fields, general: message } = mapServerError(error);
      showErrors(fields, message ?? '');
    },
  });

  const handleUpload = (event: React.FormEvent) => {
    event.preventDefault();
    if (uploadMutation.isPending || otpMutation.isPending) return;
    const found = validateApply({ fullName, email, phone, file, consent, captchaToken });
    if (Object.keys(found).length > 0 || !file || !captchaToken) {
      showErrors(found);
      return;
    }
    setErrors({});
    setGeneral('');
    uploadMutation.mutate({
      gen: generation.current,
      input: {
        fullName: fullName.trim(),
        email: email.trim(),
        phone: normalizePhone(phone),
        consent,
        captchaToken,
        file,
      },
    });
  };

  const jobsQuery = useQuery({
    queryKey: ['public-jobs', 'apply-picker'],
    queryFn: ({ signal }) => listPublicJobs({ page: 1, pageSize: 50 }, signal),
    enabled: isOpen && step === 'JOB' && !preselectedJob,
  });

  const sendOtp = () => {
    const job = preselectedJob ?? jobsQuery.data?.items.find((item) => item.id === chosenJobId) ?? null;
    if (!submission) return;
    if (!job) {
      setGeneral('Vui lòng chọn một vị trí ứng tuyển.');
      return;
    }
    if (otpMutation.isPending) return;
    setGeneral('');
    otpMutation.mutate({
      sub: submission,
      job: { id: job.id, title: job.title },
      gen: generation.current,
    });
  };

  const backToEdit = () => {
    // Liên hệ có thể đổi: bỏ submission cũ, bắt buộc tải CV và CAPTCHA lại.
    generation.current += 1;
    otpMutation.reset();
    setSubmission(null);
    setChosenJobId(null);
    setGeneral('');
    setStep('FORM');
  };

  const clearError = (field: ApplyField) => setErrors((current) => ({ ...current, [field]: undefined }));
  const describe = (field: ApplyField) => (errors[field] ? `${FIELD_IDS[field]}-error` : undefined);
  const isBusy = uploadMutation.isPending || otpMutation.isPending;

  // Thế hệ của OtpModal đang render; callback nộp hồ sơ đến muộn từ luồng cũ sẽ không khớp.
  const otpGeneration = generation.current;

  const alertBox = general && (
    <div role="alert" className="flex items-start gap-2 p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700">
      <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
      <span>{general}</span>
    </div>
  );

  return (
    <>
      <Modal isOpen={isOpen && step !== 'OTP'} onClose={close} title="Nộp hồ sơ ứng tuyển" maxWidth="2xl">
        <div id="apply-top" tabIndex={-1} className="space-y-5 outline-none">
          {step === 'FORM' && (
            <form onSubmit={handleUpload} noValidate className="space-y-5">
              {alertBox}
              {firstInvalid && (
                <section
                  id="apply-summary"
                  tabIndex={-1}
                  aria-labelledby="apply-summary-title"
                  className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 outline-none"
                >
                  <h4 id="apply-summary-title" className="font-semibold mb-1">
                    Vui lòng kiểm tra lại các thông tin sau:
                  </h4>
                  <ul className="list-disc pl-4 space-y-0.5">
                    {APPLY_FIELD_ORDER.filter((field) => errors[field]).map((field) => (
                      <li key={field}>{errors[field]}</li>
                    ))}
                  </ul>
                </section>
              )}
              {preselectedJob && (
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs">
                  <span className="text-slate-500">Vị trí ứng tuyển:</span>
                  <div className="font-bold text-slate-800 text-sm mt-0.5">{preselectedJob.title}</div>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  id={FIELD_IDS.fullName}
                  label="Họ và tên *"
                  autoComplete="name"
                  value={fullName}
                  error={errors.fullName}
                  onChange={(e) => {
                    setFullName(e.target.value);
                    clearError('fullName');
                  }}
                />
                <Input
                  id={FIELD_IDS.email}
                  label="Email *"
                  type="email"
                  autoComplete="email"
                  value={email}
                  error={errors.email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    clearError('email');
                  }}
                />
              </div>

              <Input
                id={FIELD_IDS.phone}
                label="Số điện thoại (10 chữ số) *"
                inputMode="numeric"
                autoComplete="tel"
                value={phone}
                error={errors.phone}
                onChange={(e) => {
                  setPhone(e.target.value);
                  clearError('phone');
                }}
              />

              <div>
                <label htmlFor={FIELD_IDS.file} className="block text-xs font-semibold text-slate-600 mb-1.5">
                  Tệp CV (.pdf, .docx, tối đa 5 MB) *
                </label>
                <input
                  id={FIELD_IDS.file}
                  type="file"
                  accept=".pdf,.docx"
                  aria-invalid={errors.file ? true : undefined}
                  aria-describedby={describe('file')}
                  onChange={(e) => {
                    const selected = e.target.files?.[0] ?? null;
                    setFile(selected);
                    // Kiểm tra ngay khi chọn để lỗi hiện đúng dưới ô tệp.
                    const problem = selected ? validateCvFile(selected) : undefined;
                    setErrors((current) => ({ ...current, file: problem }));
                  }}
                  className={`${FIELD_BASE} border rounded-lg p-2 ${errors.file ? 'border-rose-400' : 'border-slate-300'}`}
                />
                {file && !errors.file && <p className="mt-1 text-xs text-slate-500 break-all">Đã chọn: {file.name}</p>}
                {errors.file && (
                  <p id={`${FIELD_IDS.file}-error`} className="mt-1 text-xs text-rose-600">
                    {errors.file}
                  </p>
                )}
              </div>

              <div>
                <label className="flex items-start gap-2.5 text-xs text-slate-600 cursor-pointer p-3 bg-slate-50 border border-slate-200 rounded-xl">
                  <input
                    id={FIELD_IDS.consent}
                    type="checkbox"
                    checked={consent}
                    aria-invalid={errors.consent ? true : undefined}
                    aria-describedby={describe('consent')}
                    onChange={(e) => {
                      setConsent(e.target.checked);
                      clearError('consent');
                    }}
                    className="mt-0.5 rounded text-emerald-600 focus:ring-emerald-500"
                  />
                  <span className="leading-relaxed">
                    Tôi đồng ý cho công ty thu thập và xử lý dữ liệu cá nhân trong hồ sơ để phục vụ tuyển dụng theo Nghị định
                    13/2023/NĐ-CP.
                  </span>
                </label>
                {errors.consent && (
                  <p id={`${FIELD_IDS.consent}-error`} className="mt-1 text-xs text-rose-600">
                    {errors.consent}
                  </p>
                )}
              </div>

              <div id={FIELD_IDS.captcha} tabIndex={-1} className="outline-none overflow-x-auto">
                <TurnstileWidget
                  siteKey={env.turnstileSiteKey}
                  action="apply"
                  resetKey={captchaReset}
                  onToken={setCaptchaToken}
                />
                {errors.captcha && <p className="mt-1 text-xs text-rose-600">{errors.captcha}</p>}
              </div>

              <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-3 pt-2">
                <Button type="button" variant="outline" onClick={close}>
                  Hủy bỏ
                </Button>
                <Button type="submit" isLoading={isBusy}>
                  Tải CV lên
                </Button>
              </div>
            </form>
          )}

          {step === 'JOB' && (
            <div className="space-y-5">
              {alertBox}
              {preselectedJob ? (
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs">
                  <span className="text-slate-500">Vị trí ứng tuyển:</span>
                  <div className="font-bold text-slate-800 text-sm mt-0.5">{preselectedJob.title}</div>
                </div>
              ) : (
                <fieldset className="space-y-3">
                  <legend className="text-xs font-bold text-slate-600 mb-2">
                    Chọn vị trí ứng tuyển
                  </legend>
                  {jobsQuery.isPending && (
                    <p role="status" className="text-xs text-slate-500">
                      Đang tải danh sách vị trí...
                    </p>
                  )}
                  {jobsQuery.isError && (
                    <p className="text-xs text-rose-600">
                      Không tải được danh sách vị trí.{' '}
                      <button type="button" className="underline" onClick={() => jobsQuery.refetch()}>
                        Thử lại
                      </button>
                    </p>
                  )}
                  {jobsQuery.data?.items.length === 0 && (
                    <p className="text-xs text-slate-500">Hiện chưa có vị trí đang nhận hồ sơ.</p>
                  )}
                  {jobsQuery.data?.items.map((job) => (
                    <label
                      key={job.id}
                      className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer text-sm ${
                        chosenJobId === job.id ? 'border-emerald-500 bg-emerald-50/60' : 'border-slate-200'
                      }`}
                    >
                      <input
                        type="radio"
                        name="apply-job"
                        checked={chosenJobId === job.id}
                        onChange={() => setChosenJobId(job.id)}
                        className="mt-1"
                      />
                      <span>
                        <span className="font-bold text-slate-900">{job.title}</span>
                        <span className="block text-xs text-slate-500">
                          {job.departmentName} · {job.location}
                        </span>
                      </span>
                    </label>
                  ))}
                </fieldset>
              )}

              <div className="flex flex-col-reverse sm:flex-row sm:justify-between gap-3 pt-2">
                <Button type="button" variant="outline" size="sm" onClick={backToEdit}>
                  Quay lại sửa thông tin
                </Button>
                <Button type="button" onClick={sendOtp} isLoading={otpMutation.isPending}>
                  Gửi mã xác thực
                </Button>
              </div>
            </div>
          )}

          {step === 'DONE' && created && (
            <div className="text-center py-4 space-y-4">
              <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-10 h-10" />
              </div>
              <h3 className="text-xl font-bold text-slate-900">Đã nhận hồ sơ</h3>
              <p className="text-sm text-slate-600 max-w-md mx-auto leading-relaxed">{created.message}</p>
              <p className="text-xs text-slate-500">
                Mã hồ sơ: <span className="font-mono font-bold text-slate-800">#{created.applicationId}</span>
              </p>
              <Button onClick={close} className="w-full max-w-xs mx-auto">
                Đóng
              </Button>
            </div>
          )}
        </div>
      </Modal>

      {isOpen && step === 'OTP' && submission && targetJob && otp && (
        <OtpModal
          isOpen
          email={email.trim()}
          submissionId={submission.submissionId}
          submissionToken={submission.submissionToken}
          jobId={targetJob.id}
          expiresAt={otp.expiresAt}
          resendAvailableAt={otp.resendAvailableAt}
          onClose={close}
          onSubmitted={(result) => {
            if (otpGeneration !== generation.current) return;
            setCreated(result);
            setSubmission(null);
            setOtp(null);
            setStep('DONE');
          }}
        />
      )}
    </>
  );
};
