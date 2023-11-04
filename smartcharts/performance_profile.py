import cProfile
import pstats


def measure_performance(func):
    def wrapped_func(*args, **kwargs):
        with cProfile.Profile() as pr:
            result = func(*args, **kwargs)

        stats = pstats.Stats(pr)
        stats.sort_stats(pstats.SortKey.TIME)
        stats.dump_stats(filename=f'{func.__name__}.prof')

        return result

    return wrapped_func
