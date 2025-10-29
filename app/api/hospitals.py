from fastapi import APIRouter, Query, Depends, HTTPException
from supabase import Client
from app.core.database import get_supabase

router = APIRouter(prefix="/hospitals", tags=["hospitals"])

@router.get("")
async def get_hospitals(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    supabase: Client = Depends(get_supabase)
):
    """
    병원 목록 조회 (무한 스크롤)
    """ 
   
    response = supabase.table('hospitals')\
        .select('*')\
        .range(offset, offset + limit - 1)\
        .order('created_at', desc=False)\
        .execute()
    
    return {
        "hospitals": response.data,
        "count": len(response.data),
        "offset": offset,
        "limit": limit
    }