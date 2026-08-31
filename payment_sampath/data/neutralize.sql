-- disable sampath payment provider
UPDATE payment_provider
   SET sampath_client_id = NULL,
       sampath_auth_token = NULL,
       sampath_hmac_secret = NULL;
