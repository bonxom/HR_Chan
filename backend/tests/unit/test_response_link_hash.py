def test_token_digest_has_no_reversible_token():
    from app.core.response_links import hash_token

    token = "example-secret-token"
    assert len(hash_token(token)) == 64
    assert token not in hash_token(token)
