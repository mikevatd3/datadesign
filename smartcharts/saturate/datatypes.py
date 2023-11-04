from typing import Union
from dataclasses import dataclass, field

from .error_ops import moe_add, moe_proportion


@dataclass(frozen=True, slots=True)
class Estimate:
    value: float
    error: float | None
    numerator: float | None = None
    numerator_moe: float | None = None

    def __add__(self, other: Union[float, None, 'Estimate']) -> 'Estimate':
        if other is None:
            return self

        elif isinstance(other, float):
            return Estimate(
                self.value + other,
                self.error,
                numerator=self.numerator,
                numerator_moe=self.numerator_moe
            )
        if self.numerator_moe != None:
            raise ValueError("You cannot add another distribution to a distribution that is a numerator")
        return Estimate(
            self.value + other.value,
            moe_add(self.error, other.error),
        )

    __radd__ = __add__

    def __mul__(self, other: Union[float, 'Estimate']) -> 'Estimate':
        if (self.value is None) | (self.error is None) | (other is None):
            return self

        if isinstance(other, float):
            return Estimate(
                self.value * other,
                self.error * other,
                numerator=self.numerator,
                numerator_moe=self.numerator_moe
            )
        raise TypeError(f"Cannot multiply {type(other)} with a Estimate")

    __rmul__ = __mul__

    def __sub__(self, other: Union[float, 'Estimate']) -> 'Estimate':
        if isinstance(other, float):
            return Estimate(
                self.value - other,
                self.error
            )
        return Estimate(
            self.value - other.value,
            moe_add(self.error, other.error),
        )
    
    def __rsub__(self, other: Union[float, 'Estimate']) -> 'Estimate':
        if isinstance(other, float):
            return Estimate(
                other - self.value,
                self.error
            )
        return Estimate(
            other.value - self.value,
            moe_add(self.error, other.error),
        )

    def __truediv__(self, other: Union[float, 'Estimate']) -> 'Estimate':
        if isinstance(other, float):
            return Estimate(
                self.value / other,
                self.error,
                numerator=self.value,
                numerator_moe=round(self.error, 1)
            )
        return Estimate(
            self.value / other.value,
            moe_proportion(self.value, other.value, self.error, other.error),
            numerator=self.value,
            numerator_moe=round(self.error, 1) if self.error is not None else None
        )

    def __rtruediv__(self, other: Union[float, 'Estimate']) -> 'Estimate':
        if isinstance(other, float):
            return Estimate(
                other / self.value,
                self.error,
            )
        return Estimate(
            other.value / self.value,
            moe_proportion(other.value, self.value, other.error, self.error),
            numerator=other.value,
            numerator_moe=round(other.error, 1),
        )
    
    @property
    def error_ratio(self, precision=3) -> float | None:
        if (self.error is None) | (self.value is None):
            return None

        return round((self.error / self.value * 100), precision)


Relation = str

TerracedValue = dict[str, float | None]


@dataclass
class TerracedEstimate:
    """
    The inexplicable way that Census Reporter would like the values
    """
    values: TerracedValue = field(default_factory=dict)
    error: TerracedValue = field(default_factory=dict)
    numerators: TerracedValue = field(default_factory=dict)
    numerator_errors: TerracedValue = field(default_factory=dict)
    error_ratio: TerracedValue = field(default_factory=dict)
    index: TerracedValue = field(default_factory=dict)


