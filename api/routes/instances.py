"""
SQLGuardian - /instances routes
Register, list, and test SQL Server instances at runtime.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.db_connection import db_manager

router = APIRouter()


class RegisterInstanceRequest(BaseModel):
    name: str
    host: str
    port: int = 1433
    user: str
    password: str
    database: str = "master"
    is_default: bool = False


@router.get("/")
def list_instances():
    """List all registered SQL Server instances."""
    return {"instances": db_manager.get_registered_instances()}


@router.post("/register")
def register_instance(req: RegisterInstanceRequest):
    """Dynamically register a new SQL Server instance to monitor."""
    try:
        db_manager.register_instance(
            name=req.name,
            host=req.host,
            port=req.port,
            user=req.user,
            password=req.password,
            database=req.database,
            is_default=req.is_default,
        )
        return {"status": "registered", "instance": req.name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{instance_name}/test")
def test_instance(instance_name: str):
    """Test connectivity to a specific registered instance."""
    result = db_manager.test_connection(instance_name)
    if result["status"] != "connected":
        raise HTTPException(status_code=503, detail=result)
    return result
