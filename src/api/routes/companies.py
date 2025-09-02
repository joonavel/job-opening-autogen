"""
기업 정보 관련 API 라우터

기업 정보 조회, 검색 등의 기능을 제공합니다.
database/models.py의 Company 모델과 연동됩니다.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from ...database.fastapi_db import get_db
from ...database.models import Company, CompanyWelfare, CompanyHistory, CompanyTalentCriteria
from ...models.job_posting import CompanyData
from ..schemas.requests import CompanyInfoRequest, CompanyDetailRequest
from ..schemas.responses import (
    CompanyListResponse,
    CompanyDetailResponse,
    BaseResponse
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/search", response_model=CompanyListResponse)
async def search_companies(
    company_name: Optional[str] = Query(None, description="회사명으로 검색"),
    business_number: Optional[str] = Query(None, description="사업자등록번호로 검색"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(10, ge=1, le=100, description="페이지 크기"),
    db: Session = Depends(get_db)
) -> CompanyListResponse:
    """
    기업 정보 검색
    
    회사명이나 사업자등록번호로 기업을 검색합니다.
    """
    try:
        query = db.query(Company)
        
        # 검색 조건 적용
        if company_name:
            query = query.filter(
                Company.company_name.ilike(f"%{company_name}%")
            )
        
        if business_number:
            query = query.filter(
                Company.business_number == business_number
            )
        
        # 전체 개수 조회
        total_count = query.count()
        
        # 페이징 적용
        offset = (page - 1) * page_size
        companies_db = query.offset(offset).limit(page_size).all()
        
        # CompanyData 모델로 변환
        companies = []
        for company_db in companies_db:
            companies.append(CompanyData(
                company_name=company_db.company_name,
                company_classification=company_db.company_classification,
                homepage=company_db.homepage,
                logo_url=company_db.logo_url,
                intro_summary=company_db.intro_summary,
                intro_detail=company_db.intro_detail,
                main_business=company_db.main_business
            ))
        
        total_pages = (total_count + page_size - 1) // page_size
        
        return CompanyListResponse(
            success=True,
            message=f"{total_count}개의 기업을 찾았습니다",
            companies=companies,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.exception("Failed to search companies")
        raise HTTPException(
            status_code=500, 
            detail="기업 검색 중 오류가 발생했습니다"
        )


@router.get("/{company_id}", response_model=CompanyDetailResponse)
async def get_company_detail(
    company_id: int,
    include_welfare: bool = Query(True, description="복리후생 정보 포함 여부"),
    include_history: bool = Query(True, description="연혁 정보 포함 여부"), 
    include_talent_criteria: bool = Query(True, description="인재상 정보 포함 여부"),
    db: Session = Depends(get_db)
) -> CompanyDetailResponse:
    """
    기업 상세 정보 조회
    
    특정 기업의 상세 정보와 관련 데이터를 조회합니다.
    """
    try:
        # 기본 기업 정보 조회
        company_db = db.query(Company).filter(Company.id == company_id).first()
        
        if not company_db:
            raise HTTPException(
                status_code=404,
                detail=f"ID {company_id}에 해당하는 기업을 찾을 수 없습니다"
            )
        
        # CompanyData 모델로 변환
        company = CompanyData(
            company_name=company_db.company_name,
            company_classification=company_db.company_classification,
            homepage=company_db.homepage,
            logo_url=company_db.logo_url,
            intro_summary=company_db.intro_summary,
            intro_detail=company_db.intro_detail,
            main_business=company_db.main_business
        )
        
        # 추가 정보 조회
        welfare_items = []
        if include_welfare:
            welfare_list = db.query(CompanyWelfare).filter(
                CompanyWelfare.company_id == company_id
            ).all()
            welfare_items = [
                {
                    "category_name": item.category_name,
                    "welfare_content": item.welfare_content
                }
                for item in welfare_list
            ]
        
        history_items = []
        if include_history:
            history_list = db.query(CompanyHistory).filter(
                CompanyHistory.company_id == company_id
            ).order_by(
                CompanyHistory.history_year.desc(),
                CompanyHistory.history_month.desc()
            ).all()
            history_items = [
                {
                    "history_year": item.history_year,
                    "history_month": item.history_month,
                    "history_content": item.history_content
                }
                for item in history_list
            ]
        
        talent_criteria = []
        if include_talent_criteria:
            talent_list = db.query(CompanyTalentCriteria).filter(
                CompanyTalentCriteria.company_id == company_id
            ).all()
            talent_criteria = [
                {
                    "keyword": item.keyword,
                    "description": item.description
                }
                for item in talent_list
            ]
        
        return CompanyDetailResponse(
            success=True,
            message=f"기업 '{company.company_name}'의 상세 정보를 조회했습니다",
            company=company,
            welfare_items=welfare_items,
            history_items=history_items,
            talent_criteria=talent_criteria
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get company detail for {company_id}")
        raise HTTPException(
            status_code=500,
            detail="기업 상세 정보 조회 중 오류가 발생했습니다"
        )


@router.get("/", response_model=CompanyListResponse)
async def list_companies(
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(10, ge=1, le=100, description="페이지 크기"),
    classification: Optional[str] = Query(None, description="기업 구분별 필터"),
    db: Session = Depends(get_db)
) -> CompanyListResponse:
    """
    기업 목록 조회
    
    페이징된 기업 목록을 조회합니다.
    """
    try:
        query = db.query(Company)
        
        # 기업 구분별 필터링
        if classification:
            query = query.filter(
                Company.company_classification == classification
            )
        
        # 전체 개수 조회
        total_count = query.count()
        
        # 페이징 적용
        offset = (page - 1) * page_size
        companies_db = query.order_by(Company.company_name).offset(offset).limit(page_size).all()
        
        # CompanyData 모델로 변환
        companies = []
        for company_db in companies_db:
            companies.append(CompanyData(
                company_name=company_db.company_name,
                company_classification=company_db.company_classification,
                homepage=company_db.homepage,
                logo_url=company_db.logo_url,
                intro_summary=company_db.intro_summary,
                intro_detail=company_db.intro_detail,
                main_business=company_db.main_business
            ))
        
        total_pages = (total_count + page_size - 1) // page_size
        
        return CompanyListResponse(
            success=True,
            message=f"전체 {total_count}개 기업 중 {len(companies)}개를 조회했습니다",
            companies=companies,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.exception("Failed to list companies")
        raise HTTPException(
            status_code=500,
            detail="기업 목록 조회 중 오류가 발생했습니다"
        )


@router.get("/classifications/list", response_model=BaseResponse)
async def get_company_classifications(
    db: Session = Depends(get_db)
) -> BaseResponse:
    """
    기업 구분 목록 조회
    
    시스템에 등록된 모든 기업 구분을 조회합니다.
    """
    try:
        classifications = db.query(
            Company.company_classification,
            func.count(Company.id).label('count')
        ).filter(
            Company.company_classification.isnot(None)
        ).group_by(
            Company.company_classification
        ).all()
        
        classification_data = [
            {
                "name": classification,
                "count": count
            }
            for classification, count in classifications
        ]
        
        return BaseResponse(
            success=True,
            message=f"{len(classification_data)}개의 기업 구분을 조회했습니다",
            classifications=classification_data
        )
        
    except Exception as e:
        logger.exception("Failed to get company classifications")
        raise HTTPException(
            status_code=500,
            detail="기업 구분 목록 조회 중 오류가 발생했습니다"
        )
