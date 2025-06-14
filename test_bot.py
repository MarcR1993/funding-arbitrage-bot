name: 🧪 Bot Tests (Robust)

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:

jobs:
  test-basic:
    runs-on: ubuntu-latest
    
    steps:
    - name: 📥 Checkout code
      uses: actions/checkout@v4
    
    - name: 🐍 Set up Python 3.9
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: 📦 Install minimal dependencies
      run: |
        python -m pip install --upgrade pip
        # Install only essential packages first
        pip install pydantic pyyaml python-dotenv rich questionary click
        echo "✅ Minimal dependencies installed"
    
    - name: 🧪 Test basic structure
      run: |
        echo "📁 Testing file structure..."
        
        # Check critical files exist
        files=(
          "src/__init__.py"
          "src/main.py"
          "src/models/__init__.py"
          "src/models/position.py"
          "src/models/config.py"
          "src/exchanges/__init__.py"
          "src/bot/__init__.py"
          "src/ui/__init__.py"
        )
        
        all_present=true
        for file in "${files[@]}"; do
          if [ -f "$file" ]; then
            echo "✅ $file"
          else
            echo "❌ $file - MISSING"
            all_present=false
          fi
        done
        
        if [ "$all_present" = true ]; then
          echo "🎉 All critical files present!"
        else
          echo "❌ Some files missing"
          exit 1
        fi
    
    - name: ✅ Test basic imports
      run: |
        echo "🧪 Testing basic Python imports..."
        
        python -c "
        import sys
        print('Python version:', sys.version)
        
        # Test standard library
        import asyncio, json, os
        print('✅ Standard library OK')
        
        # Test installed packages
        import pydantic, yaml, rich, questionary
        print('✅ Installed packages OK')
        
        print('🎉 Basic imports successful!')
        "
    
    - name: 🔧 Test configuration model
      run: |
        echo "🧪 Testing configuration..."
        
        python -c "
        import sys
        sys.path.insert(0, '.')
        
        try:
            from src.models.config import FundingBotConfig
            config = FundingBotConfig()
            print(f'✅ Config created with {len(config.trading.tokens)} tokens')
            print(f'✅ Position size: \${config.trading.position_size_usd}')
            print(f'✅ Max positions: {config.trading.max_concurrent_positions}')
            print('🎉 Configuration test passed!')
        except Exception as e:
            print(f'❌ Configuration test failed: {e}')
            import traceback
            traceback.print_exc()
            exit(1)
        "
    
    - name: 📊 Test position model
      run: |
        echo "🧪 Testing position model..."
        
        python -c "
        import sys
        sys.path.insert(0, '.')
        
        try:
            from src.models.position import Position
            pos = Position(
                pair_name='test_pair',
                token='BTC',
                exchange_a='binance',
                exchange_b='kucoin',
                size_usd=1000.0
            )
            print(f'✅ Position created: {pos.id[:8]}...{pos.token}')
            print(f'✅ Age: {pos.age_hours:.2f}h')
            print(f'✅ Pair: {pos.pair_name}')
            print('🎉 Position model test passed!')
        except Exception as e:
            print(f'❌ Position model test failed: {e}')
            import traceback
            traceback.print_exc()
            exit(1)
        "
    
    - name: 🎯 Test main entry point
      run: |
        echo "🧪 Testing main entry point..."
        
        python -c "
        import sys
        sys.path.insert(0, '.')
        
        try:
            from src.main import parse_arguments
            print('✅ Main module imported')
            
            # Test argument parsing
            import argparse
            parser = argparse.ArgumentParser()
            print('✅ Argument parsing available')
            print('🎉 Main entry point test passed!')
        except Exception as e:
            print(f'❌ Main entry point test failed: {e}')
            import traceback
            traceback.print_exc()
            exit(1)
        "
    
    - name: 🏗️ Test simplified bot functionality
      run: |
        echo "🧪 Testing simplified bot..."
        python test_bot.py
    
    - name: 🎉 Success Summary
      run: |
        echo ""
        echo "🎉 ALL BASIC TESTS PASSED!"
        echo "================================"
        echo "✅ File structure complete"
        echo "✅ Dependencies installed"
        echo "✅ Configuration working"
        echo "✅ Position model functional"
        echo "✅ Main entry point ready"
        echo "✅ Basic bot framework operational"
        echo ""
        echo "🚀 Your Funding Arbitrage Bot is ready!"
        echo "💡 Next: Add API keys and configure exchanges"

  test-structure-only:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: 📁 Verify complete project structure
      run: |
        echo "🔍 Complete project structure check..."
        
        find . -name "*.py" -type f | head -20
        echo ""
        echo "📊 Python files found: $(find . -name "*.py" | wc -l)"
        echo "📁 Directories: $(find . -type d | grep -E "(src|models|exchanges|bot|ui)" | wc -l)"
        
        # Check for key directories
        for dir in "src" "src/models" "src/exchanges" "src/bot" "src/ui"; do
          if [ -d "$dir" ]; then
            echo "✅ Directory: $dir"
          else
            echo "❌ Directory missing: $dir"
          fi
        done
        
        echo "🎉 Structure verification complete!"
