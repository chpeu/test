
from ccxt.base.errors import ExchangeError

try:
    e = ExchangeError('mexc {"success":false,"code":510,"message":"Requests are too frequent"}')
    print(f"Type name: {type(e).__name__}")
    print(f"Str representation: {str(e)}")
    
    is_match = "ExchangeError" in str(type(e).__name__) and "510" in str(e)
    print(f"Match condition: {is_match}")
except Exception as ex:
    print(f"Error: {ex}")
