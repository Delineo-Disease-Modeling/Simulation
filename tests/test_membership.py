from simulator.membership import MembershipStore


def _store():
    pids = ["1", "2", "3", "4"]
    locs = [("h1", True), ("h2", True), ("f1", False)]
    return MembershipStore(pids, locs)


def test_apply_movement_and_snapshot():
    store = _store()
    patterns = {
        "60":  {"homes": {"h1": ["1", "2"], "h2": ["3", "4"]}, "places": {}},
        "120": {"homes": {"h1": ["2"], "h2": ["4"]}, "places": {"f1": ["1", "3"]}},
    }
    store.precompute_movement(patterns, max_length=10080)

    assert store.apply_movement(60)
    snap = store.movement_snapshot()
    assert snap["homes"] == {"h1": ["1", "2"], "h2": ["3", "4"]}
    assert snap["places"] == {}

    assert store.apply_movement(120)
    snap = store.movement_snapshot()
    assert snap["homes"] == {"h1": ["2"], "h2": ["4"]}
    assert snap["places"] == {"f1": ["1", "3"]}


def test_occupancy_indices():
    store = _store()
    store.precompute_movement(
        {"120": {"homes": {"h1": ["2"], "h2": ["4"]}, "places": {"f1": ["1", "3"]}}},
        max_length=10080,
    )
    store.apply_movement(120)
    view = store.occupancy_view()
    assert list(view.occupants_of(2)) == [0, 2]  # facility f1 -> persons 1,3
    assert list(view.occupants_of(0)) == [1]      # household h1 -> person 2


def test_apply_movement_unknown_ts_is_noop():
    store = _store()
    assert store.apply_movement(999) is False


def test_movement_snapshot_numeric():
    store = _store()  # 4 people; locs h1,h2 (homes), f1 (place)
    store.precompute_movement(
        {"120": {"homes": {"h1": ["1", "2"], "h2": ["4"]}, "places": {"f1": ["3"]}}},
        max_length=10080,
    )
    store.apply_movement(120)
    store.mark_infected("2")  # person 2 infected, at h1
    store.mark_infected("3")  # person 3 infected, at f1
    num = store.movement_snapshot_numeric()
    # homes order h1,h2: h1 has [1,2] count2 inf1; h2 has [4] count1 inf0
    assert num["h"] == [2, 1, 1, 0]
    # places order f1: [3] count1 inf1
    assert num["p"] == [1, 1]
