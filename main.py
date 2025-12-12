import sys
import os
from datetime import datetime
from fastapi import FastAPI
from router_v3 import route_task
from pipeline_controls import execute_pipeline

# Add seeya_repo to path for summaryflow integration
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'seeya_repo'))
from summaryflow_v3 import summarize_message

# Add chandresh_repo to path for embedding integration
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'chandresh_repo'))
from embedcore_v3 import generate_embedding

# Function to get task from Sankalp's ContextFlow
def get_task_from_contextflow(task_id: str):
    import requests
    response = requests.post('http://localhost:3000/api/contextflow_task', json={'task_id': task_id}, timeout=5)
    response.raise_for_status()
    return response.json()

# Function to send routing results to Yash's frontend
def send_to_yash_frontend(routing_result: dict, pipeline_result: dict = None):
    import requests
    import threading
    def _send():
        try:
            payload = {
                "routing": routing_result,
                "pipeline": pipeline_result,
                "timestamp": datetime.now().isoformat()
            }
            requests.post('http://localhost:4000/api/routing_result', json=payload, timeout=5)
        except Exception as e:
            print(f"Failed to send to Yash frontend: {e}")
    threading.Thread(target=_send).start()

app = FastAPI(title="OrchestratorCore v3", description="Multi-Connector Pipeline + External Routing Engine")

@app.post("/orchestrate")
async def orchestrate_task(request: dict):
    """
    Orchestrate a task: get task from ContextFlow, enrich with summary, route it and execute the pipeline.

    Input: {"task_id": str}
    Output: {"routing": routing_result, "pipeline": pipeline_result or None}
    """
    task_id = request.get('task_id')
    if not task_id:
        return {"error": "task_id required"}

    # Get task from Sankalp's ContextFlow
    try:
        task = get_task_from_contextflow(task_id)
    except Exception as e:
        return {"error": f"Failed to get task from ContextFlow: {str(e)}"}

    # Enrich task with structured summary from Seeya's SummaryFlow
    payload = {
        "user_id": task.get('user_id', 'unknown'),
        "platform": task.get('platform', 'orchestrator'),
        "message_id": task.get('task_id', task.get('message_id', 'unknown')),
        "message_text": task.get('content', task.get('message_text', str(task))),
        "timestamp": task.get('timestamp', datetime.now().isoformat())
    }
    summary = summarize_message(payload)
    task.update(summary)  # Add summary fields to task

    # Generate embedding for routing decisions (optional for future use)
    try:
        embedding = generate_embedding(task.get('content', str(task)))
        task['embedding'] = embedding
    except Exception as e:
        print(f"Embedding generation failed: {e}")

    routing_result = route_task(task)
    if routing_result["status"] == "sent":
        pipeline_result = execute_pipeline(task, routing_result["routed_to"], routing_result["trace_id"])
        result = {"routing": routing_result, "pipeline": pipeline_result}
    else:
        pipeline_result = None
        result = {"routing": routing_result, "pipeline": None}

    # Send results to Yash's frontend
    send_to_yash_frontend(routing_result, pipeline_result)
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)