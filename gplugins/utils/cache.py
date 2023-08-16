import os
import pickle
from collections.abc import Callable
from typing import Any


def disk_memoize(filename: str, overwrite: bool = False) -> Callable:
    # Check if cache file exists and load it, otherwise start with an empty cache
    if os.path.exists(filename):
        with open(filename, "rb") as f:
            cache: dict[tuple[Any] | frozenset[tuple[str, Any]], Any] = pickle.load(f)
    else:
        cache = {}

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def memoized_function(*args: Any, **kwargs: Any) -> Any:
            key = (args, frozenset(kwargs.items()))
            if key not in cache or overwrite:
                result = func(*args, **kwargs)
                cache[key] = result
                with open(filename, "wb") as f:
                    pickle.dump(cache, f)
                return result
            return cache[key]

        return memoized_function

    return decorator


if __name__ == "__main__":
    import numpy as np

    @disk_memoize("fibonacci_cache3.pkl")
    def fibonacci(n, version="v1"):
        print(f"computing fibonacci({n})")
        return np.arange(n) if version == "v1" else np.arange(n) ** 2

    print(fibonacci(4))
