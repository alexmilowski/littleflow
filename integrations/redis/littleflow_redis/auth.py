from datetime import datetime
from calendar import timegm

import jwt

def create_jwt_credential_actor(claims,private_key,kid=None,expiry=3600,issuer=None):
   def actor():
      headers = {'kid':kid} if kid is not None else {}
      payload = claims.copy()
      now = timegm(datetime.utcnow().utctimetuple())

      payload['iat'] = now
      payload['exp'] = now + expiry
      if issuer!=None:
         payload['iss'] = issuer
      if 'email' not in claims:
         payload['email'] = issuer
      if 'sub' not in claims:
         payload['sub'] = issuer

      token = jwt.encode(payload, private_key, algorithm='RS256',headers=headers)
      return token
   return actor