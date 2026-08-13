-- disable sampath payment provider
UPDATE payment_provider
   SET sampath_int_client_id = NULL,
       sampath_int_auth_token = NULL;
