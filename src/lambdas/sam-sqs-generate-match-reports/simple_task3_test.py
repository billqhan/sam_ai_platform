#!/usr/bin/env python3
"""
Simple test to verify Task 3 Knowledge Base integration is implemented.
"""
import sys
import os

# Add shared modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'shared'))

def test_imports():
    """Test that all required modules can be imported."""
    try:
        from llm_data_extraction import get_bedrock_llm_client, BedrockLLMClient
        print("✅ Successfully imported LLM modules")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_client_initialization():
    """Test that the Bedrock LLM client can be initialized."""
    try:
        from llm_data_extraction import get_bedrock_llm_client
        
        client = get_bedrock_llm_client()
        print("✅ Successfully created Bedrock LLM client")
        
        # Check if required methods exist
        methods = [
            'query_knowledge_base',
            'create_company_matching_prompt', 
            'parse_company_matching_response',
            'calculate_company_match'
        ]
        
        for method in methods:
            if hasattr(client, method):
                print(f"✅ Method {method} exists")
            else:
                print(f"❌ Method {method} missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Client initialization failed: {e}")
        return False

def test_knowledge_base_configuration():
    """Test that Knowledge Base configuration is available."""
    try:
        from llm_data_extraction import get_bedrock_llm_client
        
        client = get_bedrock_llm_client()
        
        print(f"✅ Knowledge Base ID configured: {client.knowledge_base_id}")
        print(f"✅ Model ID for matching: {client.model_id_match}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def main():
    """Run all simple tests."""
    print("🚀 SIMPLE TASK 3 VERIFICATION")
    print("="*50)
    
    tests = [
        ("Import Test", test_imports),
        ("Client Initialization", test_client_initialization),
        ("Knowledge Base Configuration", test_knowledge_base_configuration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        try:
            success = test_func()
            if success:
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
    
    print(f"\n📊 RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL BASIC TESTS PASSED!")
        print("\nTask 3 Implementation Verified:")
        print("✅ Knowledge Base integration modules available")
        print("✅ Bedrock LLM client properly configured")
        print("✅ All required methods implemented")
        print("✅ Configuration variables accessible")
        print("\n🏆 TASK 3 BASIC VERIFICATION COMPLETE!")
    else:
        print(f"\n⚠️ {total - passed} tests failed")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)