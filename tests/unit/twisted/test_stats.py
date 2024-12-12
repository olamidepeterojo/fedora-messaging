# SPDX-FileCopyrightText: 2024 Red Hat, Inc
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest

from fedora_messaging.twisted.stats import ConsumerStatistics


def test_repr():
    expected = "<ConsumerStatistics {'received': 0, 'processed': 0, 'dropped': 0, 'rejected': 0, 'failed': 0}>"
    assert repr(ConsumerStatistics()) == expected
    assert str(ConsumerStatistics()) == expected


def test_stats_add():
    stats_1 = ConsumerStatistics()
    stats_1.received = 42
    stats_1.processed = 43
    stats_2 = ConsumerStatistics()
    stats_2.received = 1
    stats_2.processed = 2
    stats_2.dropped = 10
    combined = stats_1 + stats_2
    assert combined.as_dict() == {
        "received": 43,
        "processed": 45,
        "dropped": 10,
        "rejected": 0,
        "failed": 0,
    }


def test_stats_add_bad_type():
    with pytest.raises(TypeError) as handler:
        ConsumerStatistics() + 42
    assert str(handler.value) == (
        "ConsumerStatistics instances can only be added to other ConsumerStatistics instances."
    )


def test_stats_bad_attr():
    with pytest.raises(AttributeError) as handler:
        ConsumerStatistics().dummy = 42
    assert str(handler.value) == (
        "ConsumerStatistics does not have a dummy attribute. Available attributes: dropped, "
        "failed, processed, received, rejected."
    )
