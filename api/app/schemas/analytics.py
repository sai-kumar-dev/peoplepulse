"""Aggregate-only workforce analytics response models.

No model in this module permits employee identifiers or direct personal attributes.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from api.app.schemas.common import (
    ApiModel,
    CategoryValue,
    ResponseMetadata,
    TimeValue,
)


class WorkforceSummaryResponse(ApiModel):
    as_of_date: date
    total_headcount: int = Field(ge=0)
    active_employees: int = Field(ge=0)
    inactive_employees: int = Field(ge=0)
    new_hires: int = Field(ge=0)
    terminations: int = Field(ge=0)
    attrition_rate: float = Field(ge=0, le=100)
    open_requisitions: int = Field(ge=0)
    offer_acceptance_rate: float = Field(ge=0, le=100)
    average_tenure_years: float = Field(ge=0)
    latest_refresh_time: datetime
    data_quality_score: float = Field(ge=0, le=100)
    metadata: ResponseMetadata


class HeadcountResponse(ApiModel):
    as_of_date: date
    total_headcount: int = Field(ge=0)
    trend: list[TimeValue]
    by_department: list[CategoryValue]
    by_location: list[CategoryValue]
    by_job_level: list[CategoryValue]
    by_employment_type: list[CategoryValue]
    metadata: ResponseMetadata


class AttritionTrendPoint(ApiModel):
    period: date
    terminations: int = Field(ge=0)
    average_headcount: float = Field(ge=0)
    attrition_rate: float = Field(ge=0, le=100)


class AttritionResponse(ApiModel):
    start_date: date
    end_date: date
    terminations: int = Field(ge=0)
    attrition_rate: float = Field(ge=0, le=100)
    trend: list[AttritionTrendPoint]
    by_type: list[CategoryValue]
    by_department: list[CategoryValue]
    by_tenure_band: list[CategoryValue]
    by_job_level: list[CategoryValue]
    metadata: ResponseMetadata


class HiringResponse(ApiModel):
    start_date: date
    end_date: date
    applications: int = Field(ge=0)
    offers: int = Field(ge=0)
    hires: int = Field(ge=0)
    open_requisitions: int = Field(ge=0)
    offer_acceptance_rate: float = Field(ge=0, le=100)
    average_time_to_hire_days: float = Field(ge=0)
    hiring_trend: list[TimeValue]
    recruitment_funnel: list[CategoryValue]
    by_source_channel: list[CategoryValue]
    metadata: ResponseMetadata


class MobilityResponse(ApiModel):
    start_date: date
    end_date: date
    employee_movements: int = Field(ge=0)
    promotions: int = Field(ge=0)
    transfers: int = Field(ge=0)
    promotion_rate: float = Field(ge=0, le=100)
    movement_trend: list[TimeValue]
    by_movement_type: list[CategoryValue]
    by_department: list[CategoryValue]
    metadata: ResponseMetadata


class DiversityResponse(ApiModel):
    as_of_date: date
    reportable_headcount: int = Field(ge=0)
    gender_representation: list[CategoryValue]
    workforce_by_job_level: list[CategoryValue]
    workforce_by_location: list[CategoryValue]
    suppressed_groups: int = Field(ge=0)
    metadata: ResponseMetadata


class CompensationResponse(ApiModel):
    as_of_date: date
    currency: str = Field(min_length=3, max_length=3)
    reportable_headcount: int = Field(ge=0)
    median_base_salary: float = Field(ge=0)
    average_base_salary: float = Field(ge=0)
    pay_distribution: list[CategoryValue]
    by_job_level: list[CategoryValue]
    compa_ratio_by_department: list[CategoryValue]
    suppressed_groups: int = Field(ge=0)
    metadata: ResponseMetadata


class LearningResponse(ApiModel):
    start_date: date
    end_date: date
    enrollments: int = Field(ge=0)
    completions: int = Field(ge=0)
    completion_rate: float = Field(ge=0, le=100)
    total_learning_hours: float = Field(ge=0)
    average_learning_hours: float = Field(ge=0)
    completion_trend: list[TimeValue]
    by_course_category: list[CategoryValue]
    metadata: ResponseMetadata
