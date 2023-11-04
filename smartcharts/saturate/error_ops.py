import math


def condition_arguments(*args):
    return (arg if arg is not None else 0 for arg in args) 


def moe_add(moe_a, moe_b):
    moe_a, moe_b = condition_arguments(moe_a, moe_b)
    # From http://www.census.gov/acs/www/Downloads/handbooks/ACSGeneralHandbook.pdf
    return math.sqrt(moe_a ** 2 + moe_b ** 2)


def moe_proportion(numerator, denominator, numerator_moe, denominator_moe):
    # From http://www.census.gov/acs/www/Downloads/handbooks/ACSGeneralHandbook.pdf
    # "Calculating MOEs for Derived Proportions" A-14 / A-15
    (
        numerator, 
        denominator, 
        numerator_moe, 
        denominator_moe 
    ) = condition_arguments(numerator, denominator, numerator_moe, denominator_moe)

    if denominator is 0:
        return None

    ratio = numerator / denominator

    try:
        return (
            math.sqrt(
                numerator_moe ** 2 
                - (ratio ** 2 * denominator_moe ** 2)
            )
            / denominator
        )
    except ValueError as _:
        # This seems hacky. Not sure why you'd do this.
        return moe_ratio(numerator, denominator, numerator_moe, denominator_moe)


def moe_ratio(numerator, denominator, numerator_moe, denominator_moe):
    # From http://www.census.gov/acs/www/Downloads/handbooks/ACSGeneralHandbook.pdf
    # "Calculating MOEs for Derived Ratios" A-14 / A-15
    (
        numerator, 
        denominator, 
        numerator_moe, 
        denominator_moe 
    ) = condition_arguments(numerator, denominator, numerator_moe, denominator_moe)
    
    if denominator is 0:
        return None

    ratio = numerator / denominator
    return (
        math.sqrt(numerator_moe ** 2 + (ratio ** 2 * denominator_moe ** 2))
        / denominator
    )
