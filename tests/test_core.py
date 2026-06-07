import pytest
from mathutils import add, subtract, multiply, divide, factorial, fibonacci


class TestAdd:
    def test_positive(self):
        assert add(2, 3) == 5

    def test_negative(self):
        assert add(-1, -2) == -3

    def test_zero(self):
        assert add(0, 0) == 0


class TestSubtract:
    def test_basic(self):
        assert subtract(5, 3) == 2

    def test_negative_result(self):
        assert subtract(3, 5) == -2


class TestMultiply:
    def test_basic(self):
        assert multiply(3, 4) == 12

    def test_zero(self):
        assert multiply(5, 0) == 0


class TestDivide:
    def test_basic(self):
        assert divide(10, 2) == 5.0

    def test_float_result(self):
        assert divide(7, 2) == 3.5

    def test_divide_by_zero(self):
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            divide(1, 0)


class TestFactorial:
    def test_zero(self):
        assert factorial(0) == 1

    def test_one(self):
        assert factorial(1) == 1

    def test_five(self):
        assert factorial(5) == 120

    def test_negative(self):
        with pytest.raises(ValueError):
            factorial(-1)


class TestFibonacci:
    def test_zero(self):
        assert fibonacci(0) == 0

    def test_one(self):
        assert fibonacci(1) == 1

    def test_two(self):
        assert fibonacci(2) == 1

    def test_ten(self):
        assert fibonacci(10) == 55

    def test_negative(self):
        with pytest.raises(ValueError):
            fibonacci(-1)
