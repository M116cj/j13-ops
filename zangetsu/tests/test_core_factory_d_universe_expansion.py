from zangetsu.core_factory.shadow_batch_runner import ALL14_SYMBOLS, _symbols_for_axis


def test_all14_count():
    assert len(ALL14_SYMBOLS) == 14


def test_d_uses_all14_when_mode_set():
    out = _symbols_for_axis('D', ('BTCUSDT',), 'all14')
    assert out == ALL14_SYMBOLS


def test_d_default_mode_uses_base():
    out = _symbols_for_axis('D', ('BTCUSDT', 'ETHUSDT'), 'default')
    assert out == ('BTCUSDT', 'ETHUSDT')


def test_h_c_unchanged_by_d_symbol_mode():
    h_out = _symbols_for_axis('H', ('BTCUSDT',), 'all14')
    c_out = _symbols_for_axis('C', ('BTCUSDT',), 'all14')
    assert h_out == ('BTCUSDT',)
    assert c_out == ('BTCUSDT',)
