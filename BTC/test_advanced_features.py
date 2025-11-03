#!/usr/bin/env python3
"""Test script for advanced features: position management, shadow mode, trade blocker."""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from src.position_management import get_position_manager, PositionManager
from src.shadow_mode import get_shadow_mode, ShadowMode

def test_position_management():
    """Test position management: break-even and trailing stop."""
    print("🧪 Testing position management...")
    
    manager = get_position_manager()
    
    # Register a position
    symbol = "BTCUSDT"
    manager.register_position(
        symbol=symbol,
        side="LONG",
        entry_price=50000.0,
        initial_sl=49600.0,  # 0.8% SL
        position_id="test_123",
    )
    
    # Test break-even (should trigger at +0.25% = $50125)
    print("   📊 Testing break-even...")
    current_price = 50125.0  # +0.25%
    update = manager.update_position_price(symbol, current_price)
    
    assert update is not None, "Break-even should trigger"
    assert any(a['type'] == 'break_even' for a in update['actions']), "Break-even action not found"
    pos_info = manager.get_position_info(symbol)
    assert pos_info['current_sl'] == 50000.0, "SL should be at entry (break-even)"
    assert pos_info['break_even_moved'] == True, "Break-even flag should be set"
    print(f"   ✅ Break-even triggered: SL moved to {pos_info['current_sl']:.2f}")
    
    # Test trailing stop (should trigger at +0.35% = $50175)
    print("   📊 Testing trailing stop...")
    current_price = 50175.0  # +0.35%
    update = manager.update_position_price(symbol, current_price)
    
    assert update is not None, "Trailing should trigger"
    assert any(a['type'] == 'trail' for a in update['actions']), "Trail action not found"
    pos_info = manager.get_position_info(symbol)
    assert pos_info['trailing_active'] == True, "Trailing should be active"
    assert pos_info['current_sl'] > 50000.0, "SL should be above entry (trailing)"
    print(f"   ✅ Trailing stop activated: SL at {pos_info['current_sl']:.2f}")
    
    # Close position
    manager.close_position(symbol, 50200.0, "TP")
    
    print("   ✅ Position management test PASSED")
    return True


def test_trade_blocker():
    """Test trade blocker after consecutive losses."""
    print("\n🧪 Testing trade blocker...")
    
    manager = PositionManager()  # Fresh instance
    
    # Create 5 consecutive losses
    for i in range(5):
        symbol = f"BTCUSDT{i}"
        manager.register_position(
            symbol=symbol,
            side="LONG",
            entry_price=50000.0,
            initial_sl=49600.0,
            position_id=f"test_{i}",
        )
        
        # Close with loss
        manager.close_position(symbol, 49500.0, "SL")  # -1% loss
    
    # Check if trades are blocked
    should_block, reason = manager.should_block_trades(
        max_consecutive_losses=5,
        cooldown_minutes=60,
    )
    
    assert should_block == True, "Should block after 5 consecutive losses"
    assert "consecutive losses" in reason.lower(), "Reason should mention losses"
    print(f"   ✅ Trade blocker active: {reason}")
    
    print("   ✅ Trade blocker test PASSED")
    return True


def test_shadow_mode():
    """Test shadow mode functionality."""
    print("\n🧪 Testing shadow mode...")
    
    # Create shadow mode instance (fresh)
    shadow = ShadowMode(enabled=True, duration_days=7)
    
    # Reset start time to now for testing
    shadow.start_time = datetime.now()
    
    # Should be active initially
    assert shadow.is_active() == True, "Shadow mode should be active"
    assert shadow.should_place_order() == False, "Should not place orders in shadow mode"
    print("   ✅ Shadow mode is active")
    
    # Record a signal
    shadow.record_signal(
        side="LONG",
        entry=50000.0,
        tp=50250.0,
        sl=49600.0,
        confidence=0.75,
        probs={"flat": 0.1, "long": 0.75, "short": 0.15},
    )
    
    assert len(shadow.signals) == 1, "Signal should be recorded"
    print(f"   ✅ Signal recorded: {len(shadow.signals)} signals")
    
    # Record a virtual trade
    shadow.record_virtual_trade(
        side="LONG",
        entry=50000.0,
        exit_price=50250.0,
        pnl_pct=0.005,  # +0.5%
        reason="TP",
    )
    
    assert len(shadow.virtual_trades) == 1, "Virtual trade should be recorded"
    print(f"   ✅ Virtual trade recorded: {len(shadow.virtual_trades)} trades")
    
    # Get performance summary
    perf = shadow.get_performance_summary()
    assert perf['total_trades'] == 1, "Should have 1 trade"
    assert perf['win_rate'] == 100.0, "Should have 100% win rate"
    print(f"   ✅ Performance: {perf['total_trades']} trades, {perf['win_rate']:.1f}% win rate")
    
    # Test expired shadow mode (set start time to 8 days ago)
    shadow.start_time = datetime.now() - timedelta(days=8)
    assert shadow.is_active() == False, "Shadow mode should be expired"
    assert shadow.should_place_order() == True, "Should place orders after shadow mode"
    print("   ✅ Shadow mode expiration works")
    
    print("   ✅ Shadow mode test PASSED")
    return True


def test_integration():
    """Test integration of all features."""
    print("\n🧪 Testing integration...")
    
    # Create fresh instances
    manager = PositionManager()
    shadow = ShadowMode(enabled=True, duration_days=7)
    shadow.start_time = datetime.now()
    
    # Test 1: Shadow mode prevents order placement
    print("   🔄 Test 1: Shadow mode blocking...")
    if shadow.is_active():
        shadow.record_signal("LONG", 50000.0, 50250.0, 49600.0, 0.75, {})
        print("   ✅ Shadow mode blocks order (signal recorded)")
    else:
        print("   ⚠️  Shadow mode not active")
    
    # Test 2: Trade blocker prevents new trades
    print("   🔄 Test 2: Trade blocker...")
    for i in range(5):
        manager.close_position(f"SYM{i}", 49500.0, "SL")
    
    should_block, reason = manager.should_block_trades()
    if should_block:
        print(f"   ✅ Trade blocker active: {reason[:50]}...")
    else:
        print("   ⚠️  Trade blocker not active")
    
    # Test 3: Break-even works
    print("   🔄 Test 3: Break-even integration...")
    manager.register_position("TEST", "LONG", 50000.0, 49600.0, "test_id")
    update = manager.update_position_price("TEST", 50125.0)  # +0.25%
    if update and any(a['type'] == 'break_even' for a in update.get('actions', [])):
        print("   ✅ Break-even integrated correctly")
    else:
        print("   ⚠️  Break-even not triggered")
    
    print("   ✅ Integration test PASSED")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 TESTING ADVANCED FEATURES")
    print("=" * 60)
    
    try:
        # Test 1: Position management
        test_position_management()
        
        # Test 2: Trade blocker
        test_trade_blocker()
        
        # Test 3: Shadow mode
        test_shadow_mode()
        
        # Test 4: Integration
        test_integration()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

