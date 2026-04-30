from zangetsu.core_factory import axis_registry as ar

def test_h_c_d_registered():
    ids = {a.axis_id for a in ar.list_axes()}
    assert {'H', 'C', 'D'}.issubset(ids)

def test_a_microstructure_deferred():
    a = ar.get_axis('A')
    assert a.role == 'deferred'
    assert 'bid_ask' in a.requires_data

def test_e_fallback():
    e = ar.get_axis('E')
    assert e.role == 'fallback'

def test_active_axes_excludes_deferred_and_fallback():
    active = {a.axis_id for a in ar.active_axes()}
    assert active == {'H', 'C', 'D'}
