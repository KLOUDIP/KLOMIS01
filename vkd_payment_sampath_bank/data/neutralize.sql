-- disable sampath bank payment provider
UPDATE payment_provider
   SET sampathbank_authtoken = NULL,
       sampathbank_clientId = NULL,
       sampathbank_hmac_secret = NULL,