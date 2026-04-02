import functools
import time

ENABLE_TIMER = True


def timer_decorator(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not ENABLE_TIMER:
            return func(*args, **kwargs)
        start_time = time.time()
        result = func(*args, **kwargs)
        total_time = time.time() - start_time
        print(f"{func.__name__:20} {total_time:10.2f}s")

        return result

    return wrapper
