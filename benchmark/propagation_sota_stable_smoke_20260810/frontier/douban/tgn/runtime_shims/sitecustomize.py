import random
_orig_sample = random.sample
def _kt2_sample(population, k, *args, **kwargs):
    if isinstance(population, set):
        population = sorted(population)
    return _orig_sample(population, k, *args, **kwargs)
random.sample = _kt2_sample
