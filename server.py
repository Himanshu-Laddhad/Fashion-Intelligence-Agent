"""
Flask API Backend for Fashion Intelligence
Server-side processing with enhanced scraping
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import asyncio
from pathlib import Path
import sys
import traceback
from datetime import datetime

sys.path.append(str(Path(__file__).parent))

from backend.orchestrator import run_fashion_query

app = Flask(__name__)
CORS(app)

# Configure output directory
OUTPUT_BASE = Path("outputs")
OUTPUT_BASE.mkdir(exist_ok=True)


@app.route('/api/analyze', methods=['POST'])
def analyze_fashion():
    """
    Main endpoint for fashion analysis
    POST /api/analyze
    Body: { "query": "denim jacket" }
    """
    
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({
                'error': 'Query is required',
                'status': 'error'
            }), 400
        
        print(f"\n{'='*60}")
        print(f"📥 Received request: '{query}'")
        print(f"{'='*60}\n")
        
        # Create output directory for this query
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = OUTPUT_BASE / f"{query.replace(' ', '_')}_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Run analysis (FIXED: Run async function properly)
        result = asyncio.run(run_fashion_query(query, output_dir))
        
        # Add output path to result
        result['output_directory'] = str(output_dir.absolute())
        
        print(f"\n{'='*60}")
        print(f"✅ Analysis complete for '{query}'")
        print(f"📁 Results saved to: {output_dir}")
        print(f"{'='*60}\n")
        
        return jsonify({
            'status': 'success',
            'data': result
        })
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        traceback.print_exc()
        
        return jsonify({
            'status': 'error',
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Fashion Intelligence API',
        'version': '1.0.0'
    })


@app.route('/api/outputs', methods=['GET'])
def list_outputs():
    """List all saved output directories"""
    try:
        outputs = []
        for output_dir in OUTPUT_BASE.iterdir():
            if output_dir.is_dir():
                outputs.append({
                    'name': output_dir.name,
                    'path': str(output_dir.absolute()),
                    'files': [f.name for f in output_dir.iterdir()]
                })
        
        return jsonify({
            'status': 'success',
            'outputs': outputs
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 Fashion Intelligence API Server")
    print("="*60)
    print("📍 Running on: http://localhost:5000")
    print("📊 API Endpoints:")
    print("   POST /api/analyze - Analyze fashion query")
    print("   GET  /api/health  - Health check")
    print("   GET  /api/outputs - List saved outputs")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False)  # Changed debug to False for production