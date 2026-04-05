"""Tests for parse_rating_filter."""

import pytest
from photo_cleaner.cli import parse_rating_filter


@pytest.mark.parametrize("args, expected", [
    (["none"],            {0}),
    (["1"],               {1}),
    (["1", "2"],          {1, 2}),
    (["3-5"],             {3, 4, 5}),
    (["1-1"],             {1}),
    (["5"],               {5}),
    (["none", "1", "2"],  {0, 1, 2}),
    (["none", "3-5"],     {0, 3, 4, 5}),
    (["1", "3-5"],        {1, 3, 4, 5}),
    (["none", "1", "3-5"], {0, 1, 3, 4, 5}),
    (["NONE"],            {0}),   # case-insensitive
])
def test_parse_rating_filter(args, expected):
    assert parse_rating_filter(args) == expected
