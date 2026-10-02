import time
from collections import defaultdict, deque
from threading import Lock

class RateLimiter:
    def __init__(self, limit=60, window=60):
        self.limit=limit; self.window=window; self.data=defaultdict(deque); self.lock=Lock()
    def allow(self, key):
        now=time.time()
        with self.lock:
            q=self.data[key]
            while q and q[0] <= now-self.window: q.popleft()
            if len(q)>=self.limit: return False
            q.append(now); return True
limiter=RateLimiter()
