import sys
import os
from datetime import datetime
from fastapi import FastAPI
from router_v3 import route_task
from pipeline_controls import execute_pipeline

# Add seeya_repo to path for summaryflow integration
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'seeya_repo'))
from summaryflow_v3 import summarize_message

app = FastAPI(title="OrchestratorCore v3", description="Multi-Connector Pipeline + External Routing Engine")

@app.post("/orchestrate")
async def orchestrate_task(task: dict):
    """
    Orchestrate a task: enrich with summary, route it and execute the pipeline.

    Input: task JSON dict
    Output: {"routing": routing_result, "pipeline": pipeline_result or None}
    """
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

    routing_result = route_task(task)
    if routing_result["status"] == "sent":
        pipeline_result = execute_pipeline(task, routing_result["routed_to"], routing_result["trace_id"])
        return {"routing": routing_result, "pipeline": pipeline_result}
    else:
        return {"routing": routing_result, "pipeline": None}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)