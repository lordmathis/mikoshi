from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from mikoshi.tools.manager import ToolManager

router = APIRouter()


class ApproveBody(BaseModel):
    scope: str = "once"


@router.get("/approvals")
async def get_pending_approvals(request: Request, chat_id: str):
    """Get all pending tool approvals for a chat"""
    tool_manager: ToolManager = request.app.state.tool_manager

    approvals = tool_manager.list_pending_approvals(chat_id)

    return {
        "approvals": [
            {
                "id": a["id"],
                "message_id": a["message_id"],
                "tool_name": a["tool_name"],
                "arguments": a["arguments"],
                "created_at": a["created_at"],
            }
            for a in approvals
        ]
    }


@router.post("/approvals/{approval_id}/approve")
async def approve_tool(request: Request, approval_id: str, body: ApproveBody):
    """Approve a pending tool call"""
    tool_manager: ToolManager = request.app.state.tool_manager

    try:
        result = await tool_manager.approve_tool(approval_id, scope=body.scope)
        return {"status": "approved", "result": str(result)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve tool: {str(e)}")


@router.post("/approvals/{approval_id}/deny")
async def deny_tool(request: Request, approval_id: str):
    """Deny a pending tool call"""
    tool_manager: ToolManager = request.app.state.tool_manager

    try:
        await tool_manager.deny_tool(approval_id)
        return {"status": "denied"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deny tool: {str(e)}")
