#!/usr/bin/env python3
"""
BookMaker Web App - FastAPI Backend (Multi-User)

Multi-user, multi-project book prompt adaptation using Groq API
"""

import os
from pathlib import Path
from datetime import timedelta, datetime
from typing import List, Optional
import glob
import asyncio
import ptyprocess

from fastapi import FastAPI, HTTPException, Depends, status, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from models import User, Project, ProgressLog, UserSettings, init_db, get_db
from auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    get_current_user_flexible,
    get_admin_user,
    get_password_hash,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

# Load environment variables
load_dotenv()

# Initialize database
init_db()

# Initialize FastAPI
app = FastAPI(
    title="BookMaker API",
    description="Multi-user AI-powered book prompt adaptation using Groq",
    version="3.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://book.iotok.org",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Groq client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable not set")

groq_client = Groq(api_key=GROQ_API_KEY)

# Master prompt path
MASTER_PROMPT_PATH = Path(__file__).parent.parent / "BOOK_MASTER_PROMPT.md"

# Pydantic models
class LoginRequest(BaseModel):
    username: str
    password: str

class SignupRequest(BaseModel):
    username: str
    password: str
    name: str
    email: str
    affiliation: str  # 소속

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    username: str
    user_id: int

class UserResponse(BaseModel):
    id: int
    username: str
    created_at: str

class ProjectCreate(BaseModel):
    name: str
    book_idea: str
    master_prompt_template: Optional[str] = "BOOK_MASTER_PROMPT.md"

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    book_idea: Optional[str] = None

class ProjectResponse(BaseModel):
    id: int
    user_id: int
    name: str
    book_idea: str
    master_prompt_template: Optional[str]
    adapted_prompt: Optional[str]
    user_feedback: Optional[str]
    generated_content: Optional[str]
    conversation_history: Optional[str]
    model_used: Optional[str]
    tokens_used: Optional[int]
    stage: Optional[str]
    stage_status: Optional[str]
    created_at: str
    updated_at: str

class AdaptPromptRequest(BaseModel):
    project_id: int

class AdaptPromptResponse(BaseModel):
    project_id: int
    adapted_prompt: str
    model: str
    tokens_used: int

class UserSettingsResponse(BaseModel):
    llm_provider: str
    llm_model: str
    translation_system_prompt: str
    temperature: str

class UserSettingsUpdate(BaseModel):
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    translation_system_prompt: Optional[str] = None
    temperature: Optional[str] = None

class LLMModelInfo(BaseModel):
    provider: str
    model_id: str
    display_name: str
    description: str
    available: bool = True

# Available LLM models configuration
AVAILABLE_LLM_MODELS = [
    # Groq models (verified available as of 2026-02)
    {"provider": "groq", "model_id": "llama-3.3-70b-versatile", "display_name": "Llama 3.3 70B (Groq)", "description": "Fast, versatile model from Meta via Groq"},
    {"provider": "groq", "model_id": "llama-3.1-8b-instant", "display_name": "Llama 3.1 8B Instant (Groq)", "description": "Fast, lightweight model via Groq"},
    {"provider": "groq", "model_id": "qwen/qwen3-32b", "display_name": "Qwen 3 32B (Groq)", "description": "Alibaba's Qwen 3 via Groq"},
    {"provider": "groq", "model_id": "meta-llama/llama-4-maverick-17b-128e-instruct", "display_name": "Llama 4 Maverick 17B (Groq)", "description": "Meta's Llama 4 Maverick via Groq"},
    {"provider": "groq", "model_id": "meta-llama/llama-4-scout-17b-16e-instruct", "display_name": "Llama 4 Scout 17B (Groq)", "description": "Meta's Llama 4 Scout via Groq"},
    # DeepSeek
    {"provider": "deepseek", "model_id": "deepseek-chat", "display_name": "DeepSeek Chat", "description": "DeepSeek's powerful chat model"},
    {"provider": "deepseek", "model_id": "deepseek-reasoner", "display_name": "DeepSeek Reasoner (R1)", "description": "DeepSeek's reasoning model"},
    # Qwen (Alibaba)
    {"provider": "qwen", "model_id": "qwen-turbo", "display_name": "Qwen Turbo", "description": "Alibaba's fast Qwen model"},
    {"provider": "qwen", "model_id": "qwen-plus", "display_name": "Qwen Plus", "description": "Alibaba's enhanced Qwen model"},
    {"provider": "qwen", "model_id": "qwen-max", "display_name": "Qwen Max", "description": "Alibaba's most capable Qwen model"},
    # Korean-specialized models
    {"provider": "upstage", "model_id": "solar-pro", "display_name": "Solar Pro (Upstage)", "description": "Korean AI startup's flagship model - excellent for Korean"},
    {"provider": "upstage", "model_id": "solar-mini", "display_name": "Solar Mini (Upstage)", "description": "Lightweight Korean-optimized model"},
    # LG AI Research
    {"provider": "exaone", "model_id": "exaone-3.5-32b", "display_name": "EXAONE 3.5 32B (LG)", "description": "LG's bilingual Korean-English model"},
    # GLM (Zhipu AI)
    {"provider": "glm", "model_id": "glm-4-plus", "display_name": "GLM-4 Plus", "description": "Zhipu AI's powerful model"},
    {"provider": "glm", "model_id": "glm-4-flash", "display_name": "GLM-4 Flash", "description": "Fast Zhipu AI model"},
    # Kimi (Moonshot AI)
    {"provider": "kimi", "model_id": "moonshot-v1-128k", "display_name": "Kimi Moonshot 128K", "description": "Moonshot AI's long-context model"},
]

# Authentication endpoints

@app.post("/api/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login endpoint - returns JWT token"""
    user = authenticate_user(db, request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        username=user.username,
        user_id=user.id
    )

@app.post("/api/signup", response_model=LoginResponse)
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Signup endpoint - creates new user and returns JWT token"""
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == request.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    # Validate username
    if len(request.username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be at least 3 characters"
        )

    if len(request.password) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 2 characters"
        )

    # Create new user
    new_user = User(
        username=request.username,
        password_hash=get_password_hash(request.password),
        name=request.name,
        email=request.email,
        affiliation=request.affiliation
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Generate token for auto-login
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": new_user.username}, expires_delta=access_token_expires
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        username=new_user.username,
        user_id=new_user.id
    )

@app.get("/api/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        created_at=current_user.created_at.isoformat()
    )

# User Settings endpoints

@app.get("/api/settings", response_model=UserSettingsResponse)
async def get_user_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's LLM settings"""
    settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()

    if not settings:
        # Create default settings for user
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return UserSettingsResponse(
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        translation_system_prompt=settings.translation_system_prompt,
        temperature=settings.temperature
    )

@app.put("/api/settings", response_model=UserSettingsResponse)
async def update_user_settings(
    settings_data: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's LLM settings"""
    settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()

    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)

    if settings_data.llm_provider is not None:
        settings.llm_provider = settings_data.llm_provider
    if settings_data.llm_model is not None:
        settings.llm_model = settings_data.llm_model
    if settings_data.translation_system_prompt is not None:
        settings.translation_system_prompt = settings_data.translation_system_prompt
    if settings_data.temperature is not None:
        settings.temperature = settings_data.temperature

    db.commit()
    db.refresh(settings)

    return UserSettingsResponse(
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        translation_system_prompt=settings.translation_system_prompt,
        temperature=settings.temperature
    )

@app.get("/api/available-models", response_model=List[LLMModelInfo])
async def get_available_models():
    """Get list of available LLM models with availability status"""
    # Check which providers have API keys configured
    provider_available = {
        "groq": bool(os.getenv("GROQ_API_KEY")),
        "deepseek": bool(os.getenv("DEEPSEEK_API_KEY")),
        "qwen": bool(os.getenv("DASHSCOPE_API_KEY")),
        "upstage": bool(os.getenv("UPSTAGE_API_KEY")),
        "exaone": bool(os.getenv("EXAONE_API_KEY")),
        "glm": bool(os.getenv("ZHIPU_API_KEY")),
        "kimi": bool(os.getenv("MOONSHOT_API_KEY")),
    }

    result = []
    for model in AVAILABLE_LLM_MODELS:
        model_info = model.copy()
        model_info["available"] = provider_available.get(model["provider"], False)
        if not model_info["available"]:
            model_info["description"] += " (API key not configured)"
        result.append(LLMModelInfo(**model_info))

    return result

# Project endpoints

@app.get("/api/projects", response_model=List[ProjectResponse])
async def get_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all projects for current user"""
    projects = db.query(Project).filter(Project.user_id == current_user.id).order_by(Project.updated_at.desc()).all()

    return [
        ProjectResponse(
            id=p.id,
            user_id=p.user_id,
            name=p.name,
            book_idea=p.book_idea,
            master_prompt_template=p.master_prompt_template,
            adapted_prompt=p.adapted_prompt,
            user_feedback=p.user_feedback,
            generated_content=p.generated_content,
            conversation_history=p.conversation_history,
            model_used=p.model_used,
            tokens_used=p.tokens_used,
            stage=p.stage,
            stage_status=p.stage_status,
            created_at=p.created_at.isoformat(),
            updated_at=p.updated_at.isoformat()
        )
        for p in projects
    ]

@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific project"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        book_idea=project.book_idea,
        master_prompt_template=project.master_prompt_template,
        adapted_prompt=project.adapted_prompt,
        user_feedback=project.user_feedback,
        generated_content=project.generated_content,
        conversation_history=project.conversation_history,
        model_used=project.model_used,
        tokens_used=project.tokens_used,
        stage=project.stage,
        stage_status=project.stage_status,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat()
    )

@app.post("/api/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new project"""
    project = Project(
        user_id=current_user.id,
        name=project_data.name,
        book_idea=project_data.book_idea,
        master_prompt_template=project_data.master_prompt_template
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        book_idea=project.book_idea,
        master_prompt_template=project.master_prompt_template,
        adapted_prompt=project.adapted_prompt,
        user_feedback=project.user_feedback,
        generated_content=project.generated_content,
        conversation_history=project.conversation_history,
        model_used=project.model_used,
        tokens_used=project.tokens_used,
        stage=project.stage,
        stage_status=project.stage_status,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat()
    )

@app.put("/api/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a project"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project_data.name is not None:
        project.name = project_data.name
    if project_data.book_idea is not None:
        project.book_idea = project_data.book_idea

    db.commit()
    db.refresh(project)

    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        book_idea=project.book_idea,
        master_prompt_template=project.master_prompt_template,
        adapted_prompt=project.adapted_prompt,
        user_feedback=project.user_feedback,
        generated_content=project.generated_content,
        conversation_history=project.conversation_history,
        model_used=project.model_used,
        tokens_used=project.tokens_used,
        stage=project.stage,
        stage_status=project.stage_status,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat()
    )

@app.delete("/api/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a project"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()

# Prompt adaptation endpoint

@app.post("/api/adapt-prompt", response_model=AdaptPromptResponse)
async def adapt_prompt(
    request: AdaptPromptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Adapt master prompt for a project using Groq API and save result.
    """
    # Get project
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Read master prompt template
    if not MASTER_PROMPT_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Master prompt not found at {MASTER_PROMPT_PATH}"
        )

    try:
        master_prompt = MASTER_PROMPT_PATH.read_text(encoding='utf-8')
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read master prompt: {str(e)}"
        )

    # Create system message
    system_message = """You are an expert book creation assistant and instructional designer.

Your task is to adapt a master prompt template for creating educational books. The user will provide:
1. A master prompt template (with structure, phases, and guidelines)
2. A book idea (the topic they want to write about)

You should:
- Analyze the book idea and understand its core concepts
- Adapt the master prompt's project overview, learning objectives, and chapter topics to match the new idea
- Keep the same multi-phase structure (Phase 0-8) and workflow
- Preserve formatting, code blocks, and instructional tone
- Replace example content with content relevant to the new book idea
- Maintain the bilingual (English/Korean) approach if present in the template

Return ONLY the adapted prompt without any additional commentary or explanation."""

    # Create user message
    user_message = f"""Master Prompt Template:

{master_prompt}

---

User's Book Idea:
{project.book_idea}

---

Please adapt the above master prompt template to create a comprehensive educational book about: {project.book_idea}

Specifically:
1. Update the project overview (title, subtitle, description) to match the book idea
2. Adapt chapter topics and learning objectives to the new subject
3. Modify code examples and technical content to be relevant
4. Keep the same phase-based workflow structure
5. Preserve all formatting and instructional guidelines"""

    # Get user's LLM settings
    llm_client, model_id, _, temperature = get_llm_client_for_user(current_user.id, db)

    # Call LLM API
    try:
        response = llm_client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=8000,
            top_p=0.9,
        )

        adapted_prompt = response.choices[0].message.content

        if not adapted_prompt:
            raise HTTPException(
                status_code=500,
                detail="LLM API returned empty response"
            )

        # Save to project
        project.adapted_prompt = adapted_prompt
        project.model_used = model_id
        project.tokens_used = response.usage.total_tokens
        db.commit()

        return AdaptPromptResponse(
            project_id=project.id,
            adapted_prompt=adapted_prompt,
            model=model_id,
            tokens_used=response.usage.total_tokens
        )

    except Exception as e:
        error_msg = str(e)
        if "400" in error_msg or "Bad Request" in error_msg:
            raise HTTPException(
                status_code=400,
                detail=f"LLM API rejected the request. The model '{model_id}' may be invalid or deprecated. Please update your settings."
            )
        elif "429" in error_msg or "rate limit" in error_msg.lower():
            raise HTTPException(
                status_code=429,
                detail="LLM API rate limit exceeded. Please wait a moment and try again."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"LLM API error: {error_msg}"
            )

@app.post("/api/generate-plan", response_model=AdaptPromptResponse)
async def generate_plan(
    request: AdaptPromptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate a simple book writing plan/outline for regular users.
    Creates a table of contents and rough chapter structure.
    """
    # Get project
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Create system message for plan generation
    system_message = """You are an expert book planning assistant. Your task is to create a comprehensive book writing plan based on the user's book idea.

The plan should include:
1. Book title and subtitle
2. Target audience
3. Main objectives (3-5 points)
4. Detailed table of contents with chapter titles and brief descriptions
5. Estimated length (number of pages/chapters)
6. Key themes or topics to cover

Format the output in a clear, organized manner in Korean (한글) with some English technical terms where appropriate.
Make it practical and actionable for the author."""

    # Create user message
    user_message = f"""책 아이디어:
{project.book_idea}

위 아이디어를 바탕으로 상세한 책 집필 계획을 작성해주세요. 다음 내용을 포함해야 합니다:

1. 제목 및 부제
2. 대상 독자층
3. 책의 주요 목표 (3-5개)
4. 상세한 목차 (각 챕터의 제목과 간단한 설명)
5. 예상 분량
6. 주요 테마 및 다룰 내용

독자가 이 계획을 보고 책의 전체 구조와 내용을 명확히 이해할 수 있도록 작성해주세요."""

    # Get user's LLM settings
    import logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Getting LLM settings for user {current_user.id}")
        llm_client, model_id, _, temperature = get_llm_client_for_user(current_user.id, db)
        logger.info(f"Using model: {model_id}")
    except Exception as e:
        logger.error(f"Error getting LLM settings: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting LLM settings: {str(e)}")

    # Call LLM API
    try:
        response = llm_client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=4000,
            top_p=0.9,
        )

        plan = response.choices[0].message.content

        if not plan:
            raise HTTPException(
                status_code=500,
                detail="Empty response from LLM API"
            )

        # Update project in database
        project.adapted_prompt = plan
        project.model_used = model_id
        project.tokens_used = response.usage.total_tokens
        project.stage = "1단계"  # Set stage to 1단계 after plan generation
        project.stage_status = "pending"  # Waiting for user feedback
        db.commit()

        return AdaptPromptResponse(
            project_id=project.id,
            adapted_prompt=plan,
            model=model_id,
            tokens_used=response.usage.total_tokens
        )

    except Exception as e:
        error_msg = str(e)
        # Check for common LLM API errors
        if "400" in error_msg or "Bad Request" in error_msg:
            raise HTTPException(
                status_code=400,
                detail=f"LLM API rejected the request. The model '{model_id}' may be invalid or deprecated. Please update your settings to use a different model."
            )
        elif "401" in error_msg or "Unauthorized" in error_msg:
            raise HTTPException(
                status_code=500,
                detail="LLM API authentication failed. Please contact the administrator."
            )
        elif "429" in error_msg or "rate limit" in error_msg.lower():
            raise HTTPException(
                status_code=429,
                detail="LLM API rate limit exceeded. Please wait a moment and try again."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"LLM API error: {error_msg}"
            )

class UserFeedbackRequest(BaseModel):
    project_id: int
    feedback: str

@app.post("/api/save-feedback")
async def save_user_feedback(
    request: UserFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Save user feedback on the generated plan before proceeding to writing stage.
    """
    # Get project
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Update user feedback
    project.user_feedback = request.feedback
    db.commit()

    return {"success": True, "project_id": project.id, "message": "Feedback saved successfully"}

class StageRequestModel(BaseModel):
    project_id: int
    stage: str

@app.post("/api/request-stage")
async def request_stage(
    request: StageRequestModel,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    User requests to move to a specific stage (e.g., "1단계")
    Updates the project stage field.
    """
    # Get project
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Update stage
    project.stage = request.stage
    db.commit()

    return {"success": True, "project_id": project.id, "stage": project.stage}

# Admin endpoints

class UserStats(BaseModel):
    id: int
    username: str
    created_at: str
    project_count: int
    total_tokens_used: int

class AdminProjectResponse(BaseModel):
    id: int
    user_id: int
    username: str
    name: str
    book_idea: str
    master_prompt_template: Optional[str]
    adapted_prompt: Optional[str]
    user_feedback: Optional[str]
    generated_content: Optional[str]
    model_used: Optional[str]
    tokens_used: Optional[int]
    stage: Optional[str]
    stage_status: Optional[str]
    created_at: str
    updated_at: str

class DashboardStats(BaseModel):
    total_users: int
    total_projects: int
    total_prompts_generated: int
    total_tokens_used: int
    recent_activity: List[dict]

class BookFile(BaseModel):
    filename: str
    path: str
    size: int
    modified: str

class BookGroup(BaseModel):
    project_name: str
    output_path: str
    books: List[BookFile]

@app.get("/api/admin/users", response_model=List[UserStats])
async def admin_get_users(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin: Get all users with stats"""
    from sqlalchemy import func

    users = db.query(
        User.id,
        User.username,
        User.created_at,
        func.count(Project.id).label('project_count'),
        func.coalesce(func.sum(Project.tokens_used), 0).label('total_tokens')
    ).outerjoin(Project).group_by(User.id).all()

    return [
        UserStats(
            id=u.id,
            username=u.username,
            created_at=u.created_at.isoformat(),
            project_count=u.project_count,
            total_tokens_used=int(u.total_tokens)
        )
        for u in users
    ]

@app.get("/api/admin/projects", response_model=List[AdminProjectResponse])
async def admin_get_all_projects(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin: Get all projects from all users"""
    projects = db.query(Project, User.username).join(User).order_by(Project.updated_at.desc()).all()

    return [
        AdminProjectResponse(
            id=p.Project.id,
            user_id=p.Project.user_id,
            username=p.username,
            name=p.Project.name,
            book_idea=p.Project.book_idea,
            master_prompt_template=p.Project.master_prompt_template,
            adapted_prompt=p.Project.adapted_prompt,
            user_feedback=p.Project.user_feedback,
            generated_content=p.Project.generated_content,
            model_used=p.Project.model_used,
            tokens_used=p.Project.tokens_used,
            stage=p.Project.stage,
            stage_status=p.Project.stage_status,
            created_at=p.Project.created_at.isoformat(),
            updated_at=p.Project.updated_at.isoformat()
        )
        for p in projects
    ]

@app.put("/api/admin/projects/{project_id}", response_model=AdminProjectResponse)
async def admin_update_project(
    project_id: int,
    project_data: ProjectUpdate,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin: Update any project"""
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project_data.name is not None:
        project.name = project_data.name
    if project_data.book_idea is not None:
        project.book_idea = project_data.book_idea

    db.commit()
    db.refresh(project)

    user = db.query(User).filter(User.id == project.user_id).first()

    return AdminProjectResponse(
        id=project.id,
        user_id=project.user_id,
        username=user.username,
        name=project.name,
        book_idea=project.book_idea,
        master_prompt_template=project.master_prompt_template,
        adapted_prompt=project.adapted_prompt,
        user_feedback=project.user_feedback,
        generated_content=project.generated_content,
        model_used=project.model_used,
        tokens_used=project.tokens_used,
        stage=project.stage,
        stage_status=project.stage_status,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat()
    )

@app.delete("/api/admin/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_project(
    project_id: int,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin: Delete any project"""
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()

class ProceedStageRequest(BaseModel):
    project_id: int

@app.post("/api/proceed-stage")
async def proceed_stage(
    request: ProceedStageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """User: Proceed to next stage (background processing)"""
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    current_stage = project.stage

    # CRITICAL FIX: Always commit status change BEFORE starting background thread
    # This prevents race condition where thread completes before main commit
    import threading

    if current_stage == "1단계":
        next_stage = "2단계"

        # Commit FIRST to ensure consistent DB state
        project.stage = next_stage
        project.stage_status = "in_progress"
        db.commit()

        # THEN start background thread
        thread = threading.Thread(
            target=write_book_chapters,
            args=(request.project_id, db.bind)
        )
        thread.daemon = True
        thread.start()

        return {
            "success": True,
            "project_id": project.id,
            "previous_stage": current_stage,
            "current_stage": next_stage,
            "message": "Book writing started in background"
        }
    elif current_stage == "2단계" and project.stage_status == "completed":
        next_stage = "3단계"

        # Commit FIRST
        project.stage = next_stage
        project.stage_status = "in_progress"
        db.commit()

        # THEN start thread
        thread = threading.Thread(
            target=fact_check_and_review,
            args=(request.project_id, db.bind)
        )
        thread.daemon = True
        thread.start()

        return {
            "success": True,
            "project_id": project.id,
            "previous_stage": current_stage,
            "current_stage": next_stage,
            "message": "Fact checking and critical review started in background"
        }
    elif current_stage == "3단계" and project.stage_status == "completed":
        next_stage = "4단계"

        # Commit FIRST
        project.stage = next_stage
        project.stage_status = "in_progress"
        db.commit()

        # THEN start thread
        thread = threading.Thread(
            target=generate_book_pdf,
            args=(request.project_id, db.bind)
        )
        thread.daemon = True
        thread.start()

        return {
            "success": True,
            "project_id": project.id,
            "previous_stage": current_stage,
            "current_stage": next_stage,
            "message": "PDF generation started in background"
        }
    elif current_stage == "4단계" and project.stage_status == "completed":
        next_stage = "5단계"

        # Commit FIRST
        project.stage = next_stage
        project.stage_status = "in_progress"
        db.commit()

        # THEN start thread
        thread = threading.Thread(
            target=translate_to_korean,
            args=(request.project_id, db.bind)
        )
        thread.daemon = True
        thread.start()

        return {
            "success": True,
            "project_id": project.id,
            "previous_stage": current_stage,
            "current_stage": next_stage,
            "message": "Korean translation started in background"
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot proceed from stage {current_stage} (status: {project.stage_status})"
        )

@app.post("/api/admin/proceed-stage")
async def admin_proceed_stage(
    request: ProceedStageRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin: Approve and proceed to next stage (background processing)"""
    project = db.query(Project).filter(Project.id == request.project_id).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    current_stage = project.stage

    # CRITICAL FIX: Always commit status change BEFORE starting background thread
    import threading

    if current_stage == "1단계":
        next_stage = "2단계"

        # Commit FIRST
        project.stage = next_stage
        project.stage_status = "in_progress"
        db.commit()

        # THEN start thread
        thread = threading.Thread(
            target=write_book_chapters,
            args=(request.project_id, db.bind)
        )
        thread.daemon = True
        thread.start()

        return {
            "success": True,
            "project_id": project.id,
            "previous_stage": current_stage,
            "current_stage": next_stage,
            "message": "Book writing started in background"
        }
    elif current_stage == "2단계" and project.stage_status == "completed":
        next_stage = "3단계"

        # Commit FIRST
        project.stage = next_stage
        project.stage_status = "in_progress"
        db.commit()

        # THEN start thread
        thread = threading.Thread(
            target=fact_check_and_review,
            args=(request.project_id, db.bind)
        )
        thread.daemon = True
        thread.start()

        return {
            "success": True,
            "project_id": project.id,
            "previous_stage": current_stage,
            "current_stage": next_stage,
            "message": "Fact checking and critical review started in background"
        }
    elif current_stage == "3단계" and project.stage_status == "completed":
        next_stage = "4단계"

        # Commit FIRST
        project.stage = next_stage
        project.stage_status = "in_progress"
        db.commit()

        # THEN start thread
        thread = threading.Thread(
            target=generate_book_pdf,
            args=(request.project_id, db.bind)
        )
        thread.daemon = True
        thread.start()

        return {
            "success": True,
            "project_id": project.id,
            "previous_stage": current_stage,
            "current_stage": next_stage,
            "message": "PDF generation started in background"
        }
    elif current_stage == "4단계" and project.stage_status == "completed":
        next_stage = "5단계"

        # Commit FIRST
        project.stage = next_stage
        project.stage_status = "in_progress"
        db.commit()

        # THEN start thread
        thread = threading.Thread(
            target=translate_to_korean,
            args=(request.project_id, db.bind)
        )
        thread.daemon = True
        thread.start()

        return {
            "success": True,
            "project_id": project.id,
            "previous_stage": current_stage,
            "current_stage": next_stage,
            "message": "Korean translation started in background"
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot proceed from stage {current_stage} (status: {project.stage_status})"
        )

class RefineChapterRequest(BaseModel):
    project_id: int
    user_prompt: str

@app.post("/api/refine-chapter")
async def refine_chapter(
    request: RefineChapterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Iterative chapter refinement based on user prompts.
    User can request rewrites of specific chapters.
    """
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.stage != "2단계" or not project.generated_content:
        raise HTTPException(
            status_code=400,
            detail="Can only refine chapters after initial writing is completed"
        )

    # Parse user prompt to identify chapter number
    import re
    chapter_match = re.search(r'chapter\s*(\d+)', request.user_prompt, re.IGNORECASE)

    if not chapter_match:
        # If no specific chapter mentioned, return error
        return {
            "success": False,
            "message": "Please specify a chapter number (e.g., 'Write Chapter 3 with detail')"
        }

    chapter_num = int(chapter_match.group(1))

    # Add to conversation history
    import json
    conversation = json.loads(project.conversation_history) if project.conversation_history else []
    conversation.append({
        "role": "user",
        "content": request.user_prompt,
        "timestamp": datetime.utcnow().isoformat()
    })

    # Extract current chapter content
    content = project.generated_content
    chapter_pattern = rf'## Chapter {chapter_num}: ([^\n]+)'
    chapter_title_match = re.search(chapter_pattern, content)

    if not chapter_title_match:
        return {
            "success": False,
            "message": f"Chapter {chapter_num} not found in the book"
        }

    chapter_title = chapter_title_match.group(1).strip()

    # Log the refinement request
    log = ProgressLog(
        project_id=project.id,
        stage="2단계",
        message=f"✍️ User requested: {request.user_prompt}",
        level="info"
    )
    db.add(log)
    db.commit()

    # Create refinement prompt
    system_message = """You are an expert book writer. The user wants to refine a specific chapter.

CRITICAL REQUIREMENTS:
- Write ONLY in English language
- Follow the user's specific instructions
- Maintain consistent style with the rest of the book
- Use clear, educational prose
- Include practical examples and detailed explanations"""

    user_message = f"""Refine this chapter based on the user's request.

Book Title: {project.name}
Book Subject: {project.book_idea}

Chapter {chapter_num}: {chapter_title}

User Request: {request.user_prompt}

Book Plan Context:
{project.adapted_prompt[:800] if project.adapted_prompt else ''}

User Feedback on Overall Book:
{project.user_feedback if project.user_feedback else 'None provided'}

Write the COMPLETE refined chapter in English with enhanced detail and quality:"""

    try:
        # Get user's LLM settings
        llm_client, model_id, _, temperature = get_llm_client_for_user(current_user.id, db)

        # Call LLM API
        response = llm_client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=4000,
            top_p=0.9
        )

        refined_chapter = response.choices[0].message.content
        tokens_used = response.usage.total_tokens

        # Replace the chapter in generated_content
        # Find chapter boundaries
        all_chapters = re.finditer(r'## Chapter (\d+): ([^\n]+)', content)
        chapters_list = list(all_chapters)

        # Find the target chapter and the next chapter
        target_idx = None
        for idx, match in enumerate(chapters_list):
            if int(match.group(1)) == chapter_num:
                target_idx = idx
                break

        if target_idx is not None:
            start_pos = chapters_list[target_idx].start()
            if target_idx + 1 < len(chapters_list):
                end_pos = chapters_list[target_idx + 1].start()
            else:
                end_pos = len(content)

            # Replace the chapter
            new_content = content[:start_pos] + f"## Chapter {chapter_num}: {chapter_title}\n\n" + refined_chapter + "\n\n---\n\n" + content[end_pos:]
            project.generated_content = new_content

        # Update tokens
        project.tokens_used = (project.tokens_used or 0) + tokens_used

        # Add AI response to conversation
        conversation.append({
            "role": "assistant",
            "content": f"Chapter {chapter_num} has been refined ({tokens_used} tokens used)",
            "timestamp": datetime.utcnow().isoformat()
        })
        project.conversation_history = json.dumps(conversation)

        db.commit()

        # Log completion
        log = ProgressLog(
            project_id=project.id,
            stage="2단계",
            message=f"✅ Refined Chapter {chapter_num}: {chapter_title} ({tokens_used} tokens)",
            level="success"
        )
        db.add(log)
        db.commit()

        return {
            "success": True,
            "message": f"Chapter {chapter_num} refined successfully",
            "chapter_number": chapter_num,
            "chapter_title": chapter_title,
            "tokens_used": tokens_used,
            "refined_content": refined_chapter
        }

    except Exception as e:
        # Log error
        log = ProgressLog(
            project_id=project.id,
            stage="2단계",
            message=f"❌ Error refining chapter: {str(e)}",
            level="error"
        )
        db.add(log)
        db.commit()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to refine chapter: {str(e)}"
        )

def add_log(db_engine, project_id: int, stage: str, message: str, level: str = "info"):
    """Add a progress log entry"""
    from sqlalchemy.orm import Session as SQLSession
    db = SQLSession(bind=db_engine)
    try:
        log = ProgressLog(
            project_id=project_id,
            stage=stage,
            message=message,
            level=level
        )
        db.add(log)
        db.commit()
    finally:
        db.close()

def perform_web_search(query: str, max_results: int = 5) -> str:
    """Perform web search and return summarized results"""
    try:
        import requests
        from bs4 import BeautifulSoup

        # Use DuckDuckGo HTML search (no API key required)
        search_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        results = []
        for result in soup.find_all('div', class_='result')[:max_results]:
            title_elem = result.find('a', class_='result__a')
            snippet_elem = result.find('a', class_='result__snippet')

            if title_elem and snippet_elem:
                title = title_elem.get_text(strip=True)
                snippet = snippet_elem.get_text(strip=True)
                results.append(f"- {title}: {snippet}")

        if results:
            return "\n".join(results)
        else:
            return "No search results found."
    except Exception as e:
        return f"Search error: {str(e)}"

def write_book_chapters(project_id: int, db_engine):
    """Background task to write book chapters using Groq API with web search"""
    from sqlalchemy.orm import Session as SQLSession
    import time

    db = SQLSession(bind=db_engine)

    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return

        # Get user's LLM settings
        llm_client, model_id, _, temperature = get_llm_client_for_user(project.user_id, db)
        add_log(db_engine, project_id, "2단계", f"🤖 Using model: {model_id}", "info")
        add_log(db_engine, project_id, "2단계", "🚀 Starting English book writing process", "info")

        # Perform web search for background information
        add_log(db_engine, project_id, "2단계", "🔍 Performing web search for background research", "info")
        search_query = f"{project.name} {project.book_idea[:100]}"
        search_results = perform_web_search(search_query, max_results=3)
        add_log(db_engine, project_id, "2단계", "✅ Web search completed", "success")
        time.sleep(1)

        # Parse the adapted_prompt to extract chapter structure
        plan_text = project.adapted_prompt or ""
        user_feedback = project.user_feedback or ""

        add_log(db_engine, project_id, "2단계", "📋 Analyzing book plan and structure", "info")
        if user_feedback:
            add_log(db_engine, project_id, "2단계", f"📝 User feedback received: {user_feedback[:100]}...", "info")
        time.sleep(1)

        # Extract chapters from the plan
        import re
        chapter_matches = re.findall(r'\d+\.\s\*\*([^*]+)\*\*', plan_text)
        if not chapter_matches:
            # Try alternative format
            chapter_matches = re.findall(r'- Ch\d+:\s*([^\n]+)', plan_text)

        if not chapter_matches:
            # Fallback: create default chapters
            chapter_matches = [
                "Introduction",
                "Core Concepts",
                "Practical Applications",
                "Advanced Topics",
                "Case Studies",
                "Troubleshooting",
                "Future Directions",
                "Conclusion"
            ]

        add_log(db_engine, project_id, "2단계", f"📚 Found {len(chapter_matches)} chapters to write", "success")

        book_content = f"# {project.name}\n\n"
        book_content += f"**Book Idea:** {project.book_idea}\n\n"
        book_content += "---\n\n"

        total_tokens = 0

        for idx, chapter_title in enumerate(chapter_matches, 1):
            chapter_title = chapter_title.strip()
            add_log(db_engine, project_id, "2단계", f"✍️ Writing Chapter {idx}: {chapter_title}", "info")

            # Create chapter writing prompt
            system_message = f"""You are an expert English-language book writer specializing in educational content.

CRITICAL REQUIREMENTS:
- You MUST write ONLY in English language
- Even if the context or plan is in another language, write your output in English
- Use clear, educational English prose suitable for international readers
- Follow best practices from educational textbook writing
- Structure content with proper headings, examples, and explanations"""

            # Build user message with feedback and search results
            feedback_section = f"\n\nUser Feedback on Plan:\n{user_feedback}\n" if user_feedback else ""
            search_section = f"\n\nWeb Research Results:\n{search_results}\n" if idx == 1 else ""  # Include search results in first chapter

            user_message = f"""Write Chapter {idx} for this educational book.

Chapter Title: {chapter_title}
Book Title: {project.name}
Book Subject: {project.book_idea}

Book Plan Reference (may be in different language - translate concepts to English):
{plan_text[:800]}{feedback_section}{search_section}

WRITING REQUIREMENTS:
- MANDATORY: Write the ENTIRE chapter in English language only
- Target audience: General readers interested in the subject
- Length: 800-1200 words
- Format: Use markdown with ## headings, bullet lists, code blocks where relevant
- Style: Clear, educational, practical with real examples
- Structure: Introduction → Core concepts → Practical applications → Summary
- If user feedback is provided, incorporate those suggestions into your writing

IMPORTANT: Even if the chapter title or plan is in Korean/other language, write ALL content in English.

Write the complete chapter now in English:"""

            try:
                response = llm_client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.7,
                    max_tokens=3000,
                    top_p=0.9
                )

                chapter_content = response.choices[0].message.content
                total_tokens += response.usage.total_tokens

                book_content += f"\n\n## Chapter {idx}: {chapter_title}\n\n"
                book_content += chapter_content
                book_content += "\n\n---\n\n"

                add_log(db_engine, project_id, "2단계",
                       f"✅ Completed Chapter {idx}: {chapter_title} ({response.usage.total_tokens} tokens)",
                       "success")

                # Update project with progress
                project.generated_content = book_content
                project.tokens_used = (project.tokens_used or 0) + total_tokens
                db.commit()

                time.sleep(0.5)  # Small delay between chapters

            except Exception as e:
                add_log(db_engine, project_id, "2단계",
                       f"❌ Error writing Chapter {idx}: {str(e)}",
                       "error")

        # Finalize - use explicit update for reliability with background threads
        from sqlalchemy import update
        db.execute(
            update(Project)
            .where(Project.id == project_id)
            .values(generated_content=book_content, stage_status="completed")
        )
        db.commit()

        add_log(db_engine, project_id, "2단계",
               f"🎉 English writing finished! Total: {len(chapter_matches)} chapters, {total_tokens} tokens",
               "success")

    except Exception as e:
        add_log(db_engine, project_id, "2단계", f"❌ Fatal error: {str(e)}", "error")
        from sqlalchemy import update
        db.execute(update(Project).where(Project.id == project_id).values(stage_status="error"))
        db.commit()
    finally:
        db.close()

def generate_book_pdf(project_id: int, db_engine):
    """Background task to generate PDF from book content using pandoc"""
    from sqlalchemy.orm import Session as SQLSession
    import subprocess
    import time
    import shutil

    db = SQLSession(bind=db_engine)

    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project or not project.generated_content:
            add_log(db_engine, project_id, "4단계", "❌ No content found for PDF generation", "error")
            return

        add_log(db_engine, project_id, "4단계", "📄 Starting PDF generation", "info")
        time.sleep(0.5)

        # Create output directory
        output_dir = Path(f"/var/www/aibook/bookmaker/backend/output/user_{project.user_id}")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize project name for filename
        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in project.name)
        safe_name = safe_name.strip().replace(' ', '_')[:50]
        if not safe_name:
            safe_name = f"book_{project.id}"

        md_file = output_dir / f"{safe_name}.md"
        pdf_file = output_dir / f"{safe_name}.pdf"

        # Write markdown content to file
        add_log(db_engine, project_id, "4단계", "📝 Preparing markdown content", "info")

        # Add front matter and cleanup content
        content = project.generated_content

        # Write to markdown file
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(content)

        add_log(db_engine, project_id, "4단계", f"✅ Markdown saved: {md_file.name}", "success")
        time.sleep(0.5)

        # Generate PDF using pandoc
        add_log(db_engine, project_id, "4단계", "🔄 Converting to PDF with pandoc...", "info")

        try:
            result = subprocess.run(
                [
                    'pandoc',
                    str(md_file),
                    '-o', str(pdf_file),
                    '--pdf-engine=xelatex',
                    '-V', 'geometry:margin=1in',
                    '-V', 'fontsize=11pt',
                    '--toc',
                    '--toc-depth=2',
                    '-V', 'colorlinks=true',
                    '-V', 'linkcolor=blue',
                ],
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )

            if result.returncode != 0:
                add_log(db_engine, project_id, "4단계",
                       f"⚠️ Pandoc warning: {result.stderr[:200] if result.stderr else 'Unknown error'}",
                       "warning")
                # Try simpler conversion without TOC
                result = subprocess.run(
                    [
                        'pandoc',
                        str(md_file),
                        '-o', str(pdf_file),
                        '--pdf-engine=xelatex',
                        '-V', 'geometry:margin=1in',
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120
                )

            if pdf_file.exists():
                file_size = pdf_file.stat().st_size
                add_log(db_engine, project_id, "4단계",
                       f"✅ PDF generated: {pdf_file.name} ({file_size // 1024} KB)",
                       "success")

                # Store the PDF path in project - use explicit update for reliability
                new_content = project.generated_content + f"\n\n<!-- PDF_PATH:{pdf_file} -->"
                from sqlalchemy import update
                db.execute(
                    update(Project)
                    .where(Project.id == project_id)
                    .values(generated_content=new_content, stage_status="completed")
                )
                db.commit()

                add_log(db_engine, project_id, "4단계",
                       f"🎉 Book creation completed! PDF ready for download.",
                       "success")
            else:
                add_log(db_engine, project_id, "4단계",
                       f"❌ PDF generation failed: {result.stderr[:300] if result.stderr else 'Unknown error'}",
                       "error")
                from sqlalchemy import update
                db.execute(update(Project).where(Project.id == project_id).values(stage_status="error"))
                db.commit()

        except subprocess.TimeoutExpired:
            add_log(db_engine, project_id, "4단계", "❌ PDF generation timed out", "error")
            from sqlalchemy import update
            db.execute(update(Project).where(Project.id == project_id).values(stage_status="error"))
            db.commit()

    except Exception as e:
        add_log(db_engine, project_id, "4단계", f"❌ Fatal error: {str(e)}", "error")
        from sqlalchemy import update
        db.execute(update(Project).where(Project.id == project_id).values(stage_status="error"))
        db.commit()
    finally:
        db.close()


def get_llm_client_for_user(user_id: int, db):
    """Get the appropriate LLM client based on user settings"""
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()

    if not settings:
        # Use default Groq client
        return groq_client, "llama-3.3-70b-versatile", None, "0.3"

    provider = settings.llm_provider
    model = settings.llm_model
    system_prompt = settings.translation_system_prompt
    temperature = settings.temperature

    if provider == "groq":
        return groq_client, model, system_prompt, temperature
    elif provider == "deepseek":
        # DeepSeek uses OpenAI-compatible API
        from openai import OpenAI
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key:
            client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
            return client, model, system_prompt, temperature
        else:
            return groq_client, "llama-3.3-70b-versatile", system_prompt, temperature
    elif provider == "qwen":
        # Qwen uses DashScope API (OpenAI-compatible)
        from openai import OpenAI
        qwen_key = os.getenv("DASHSCOPE_API_KEY")
        if qwen_key:
            client = OpenAI(api_key=qwen_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
            return client, model, system_prompt, temperature
        else:
            return groq_client, "llama-3.3-70b-versatile", system_prompt, temperature
    elif provider == "upstage":
        # Solar uses Upstage API (OpenAI-compatible)
        from openai import OpenAI
        upstage_key = os.getenv("UPSTAGE_API_KEY")
        if upstage_key:
            client = OpenAI(api_key=upstage_key, base_url="https://api.upstage.ai/v1/solar")
            return client, model, system_prompt, temperature
        else:
            return groq_client, "llama-3.3-70b-versatile", system_prompt, temperature
    elif provider == "exaone":
        # LG EXAONE - use their API
        from openai import OpenAI
        exaone_key = os.getenv("EXAONE_API_KEY")
        if exaone_key:
            client = OpenAI(api_key=exaone_key, base_url="https://api.exaone.ai/v1")
            return client, model, system_prompt, temperature
        else:
            return groq_client, "llama-3.3-70b-versatile", system_prompt, temperature
    elif provider == "glm":
        # GLM uses Zhipu API
        from openai import OpenAI
        glm_key = os.getenv("ZHIPU_API_KEY")
        if glm_key:
            client = OpenAI(api_key=glm_key, base_url="https://open.bigmodel.cn/api/paas/v4")
            return client, model, system_prompt, temperature
        else:
            return groq_client, "llama-3.3-70b-versatile", system_prompt, temperature
    elif provider == "kimi":
        # Kimi uses Moonshot API
        from openai import OpenAI
        kimi_key = os.getenv("MOONSHOT_API_KEY")
        if kimi_key:
            client = OpenAI(api_key=kimi_key, base_url="https://api.moonshot.cn/v1")
            return client, model, system_prompt, temperature
        else:
            return groq_client, "llama-3.3-70b-versatile", system_prompt, temperature
    else:
        return groq_client, "llama-3.3-70b-versatile", system_prompt, temperature


def translate_to_korean(project_id: int, db_engine):
    """Background task to translate book content to Korean and generate Korean PDF"""
    from sqlalchemy.orm import Session as SQLSession
    import subprocess
    import time
    import re

    db = SQLSession(bind=db_engine)

    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project or not project.generated_content:
            add_log(db_engine, project_id, "5단계", "❌ No content found for translation", "error")
            return

        # Get user's LLM settings
        llm_client, model_id, custom_system_prompt, temperature = get_llm_client_for_user(project.user_id, db)
        add_log(db_engine, project_id, "5단계", f"🤖 Using model: {model_id}", "info")
        add_log(db_engine, project_id, "5단계", "🌐 Starting Korean translation", "info")
        time.sleep(0.5)

        # Get the English content (remove PDF path comment if present)
        content = project.generated_content
        content = re.sub(r'\n\n<!-- PDF_PATH:[^>]+ -->', '', content)

        # Parse chapters
        chapter_pattern = r'## Chapter (\d+): ([^\n]+)'
        chapter_matches = list(re.finditer(chapter_pattern, content))

        if not chapter_matches:
            add_log(db_engine, project_id, "5단계", "❌ No chapters found to translate", "error")
            from sqlalchemy import update
            db.execute(update(Project).where(Project.id == project_id).values(stage_status="error"))
            db.commit()
            return

        add_log(db_engine, project_id, "5단계", f"📚 Found {len(chapter_matches)} chapters to translate", "info")

        # Translate title
        korean_content = ""

        # Extract and translate book title
        title_match = re.match(r'# ([^\n]+)', content)
        if title_match:
            book_title = title_match.group(1)
            add_log(db_engine, project_id, "5단계", f"🔄 Translating book title: {book_title}", "info")

            try:
                title_response = llm_client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": "You are a professional Korean translator. Translate the given English text to natural Korean. Return ONLY the translated text, nothing else. Do NOT output Chinese characters."},
                        {"role": "user", "content": f"Translate this book title to Korean:\n{book_title}"}
                    ],
                    temperature=float(temperature),
                    max_tokens=200
                )
                korean_title = title_response.choices[0].message.content.strip()
                korean_content = f"# {korean_title}\n\n"
                add_log(db_engine, project_id, "5단계", f"✅ Title translated: {korean_title}", "success")
            except Exception as e:
                korean_content = f"# {book_title}\n\n"
                add_log(db_engine, project_id, "5단계", f"⚠️ Title translation failed: {str(e)[:100]}", "warning")

        # Add book idea in Korean
        korean_content += f"**원본 아이디어:** {project.book_idea}\n\n"
        korean_content += "---\n\n"

        total_tokens = 0

        # Translate each chapter
        for i, match in enumerate(chapter_matches):
            chapter_num = int(match.group(1))
            chapter_title = match.group(2).strip()

            # Get chapter content
            start_pos = match.start()
            end_pos = chapter_matches[i + 1].start() if i + 1 < len(chapter_matches) else len(content)
            chapter_content = content[start_pos:end_pos].strip()

            add_log(db_engine, project_id, "5단계", f"🔄 Translating Chapter {chapter_num}: {chapter_title}", "info")

            try:
                # Use custom system prompt if provided, otherwise use default
                default_system_prompt = """You are a professional Korean translator specializing in educational books.

TRANSLATION GUIDELINES:
- Translate all English text to natural, fluent Korean (한글)
- Use formal Korean style (존댓말/합쇼체)
- Keep technical terms in English with Korean explanation in parentheses when first introduced
- Preserve all markdown formatting (##, **, -, code blocks, etc.)
- Keep code examples in English but translate comments to Korean
- Maintain the educational tone suitable for Korean readers
- Do NOT add any translator notes or explanations outside the content
- Do NOT output Chinese characters under any circumstances
- Do NOT include random code snippets that are not part of the original content"""

                system_prompt = custom_system_prompt if custom_system_prompt else default_system_prompt

                # Translate the chapter
                response = llm_client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Translate this chapter to Korean:\n\n{chapter_content}"}
                    ],
                    temperature=float(temperature),
                    max_tokens=4000
                )

                translated_chapter = response.choices[0].message.content
                total_tokens += response.usage.total_tokens

                korean_content += translated_chapter + "\n\n---\n\n"

                add_log(db_engine, project_id, "5단계",
                       f"✅ Completed Chapter {chapter_num} ({response.usage.total_tokens} tokens)",
                       "success")

                time.sleep(0.5)  # Small delay between chapters

            except Exception as e:
                add_log(db_engine, project_id, "5단계",
                       f"❌ Error translating Chapter {chapter_num}: {str(e)}",
                       "error")
                # Add original chapter if translation fails
                korean_content += chapter_content + "\n\n---\n\n"

        add_log(db_engine, project_id, "5단계",
               f"✅ Translation completed! Total: {total_tokens} tokens",
               "success")

        # Save Korean content
        # Store Korean content in a special field or append to generated_content
        # For now, we'll create the Korean PDF directly

        # Create output directory
        output_dir = Path(f"/var/www/aibook/bookmaker/backend/output/user_{project.user_id}")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize project name for filename
        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in project.name)
        safe_name = safe_name.strip().replace(' ', '_')[:50]
        if not safe_name:
            safe_name = f"book_{project.id}"

        korean_md_file = output_dir / f"{safe_name}_KO.md"
        korean_pdf_file = output_dir / f"{safe_name}_KO.pdf"

        # Write Korean markdown
        add_log(db_engine, project_id, "5단계", "📝 Saving Korean markdown", "info")
        with open(korean_md_file, 'w', encoding='utf-8') as f:
            f.write(korean_content)

        add_log(db_engine, project_id, "5단계", f"✅ Korean markdown saved: {korean_md_file.name}", "success")

        # Generate Korean PDF
        add_log(db_engine, project_id, "5단계", "🔄 Generating Korean PDF...", "info")

        try:
            # Use XeLaTeX with Korean font support
            result = subprocess.run(
                [
                    'pandoc',
                    str(korean_md_file),
                    '-o', str(korean_pdf_file),
                    '--pdf-engine=xelatex',
                    '-V', 'geometry:margin=1in',
                    '-V', 'fontsize=11pt',
                    '-V', 'mainfont=Noto Sans CJK KR',
                    '-V', 'CJKmainfont=Noto Sans CJK KR',
                    '--toc',
                    '--toc-depth=2',
                    '-V', 'colorlinks=true',
                    '-V', 'linkcolor=blue',
                ],
                capture_output=True,
                text=True,
                timeout=180  # 3 minute timeout for Korean PDF
            )

            if result.returncode != 0:
                add_log(db_engine, project_id, "5단계",
                       f"⚠️ Pandoc warning: {result.stderr[:200] if result.stderr else 'Unknown'}",
                       "warning")
                # Try simpler conversion
                result = subprocess.run(
                    [
                        'pandoc',
                        str(korean_md_file),
                        '-o', str(korean_pdf_file),
                        '--pdf-engine=xelatex',
                        '-V', 'geometry:margin=1in',
                        '-V', 'mainfont=Noto Sans CJK KR',
                    ],
                    capture_output=True,
                    text=True,
                    timeout=180
                )

            if korean_pdf_file.exists():
                file_size = korean_pdf_file.stat().st_size
                add_log(db_engine, project_id, "5단계",
                       f"✅ Korean PDF generated: {korean_pdf_file.name} ({file_size // 1024} KB)",
                       "success")

                # Get current tokens and update using explicit SQL for reliability
                current_tokens = db.query(Project.tokens_used).filter(Project.id == project_id).scalar() or 0
                from sqlalchemy import update
                db.execute(
                    update(Project)
                    .where(Project.id == project_id)
                    .values(tokens_used=current_tokens + total_tokens, stage_status="completed")
                )
                db.commit()

                add_log(db_engine, project_id, "5단계",
                       "🎉 Korean translation completed! PDF ready for download.",
                       "success")
            else:
                add_log(db_engine, project_id, "5단계",
                       f"❌ Korean PDF generation failed: {result.stderr[:300] if result.stderr else 'Unknown'}",
                       "error")
                from sqlalchemy import update
                db.execute(update(Project).where(Project.id == project_id).values(stage_status="error"))
                db.commit()

        except subprocess.TimeoutExpired:
            add_log(db_engine, project_id, "5단계", "❌ Korean PDF generation timed out", "error")
            from sqlalchemy import update
            db.execute(update(Project).where(Project.id == project_id).values(stage_status="error"))
            db.commit()

    except Exception as e:
        add_log(db_engine, project_id, "5단계", f"❌ Fatal error: {str(e)}", "error")
        from sqlalchemy import update
        db.execute(update(Project).where(Project.id == project_id).values(stage_status="error"))
        db.commit()
    finally:
        db.close()


def fact_check_and_review(project_id: int, db_engine):
    """Background task to fact-check and critically review the book content"""
    from sqlalchemy.orm import Session as SQLSession
    import time

    db = SQLSession(bind=db_engine)

    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project or not project.generated_content:
            return

        # Get user's LLM settings
        llm_client, model_id, _, temperature = get_llm_client_for_user(project.user_id, db)
        add_log(db_engine, project_id, "3단계", f"🤖 Using model: {model_id}", "info")
        add_log(db_engine, project_id, "3단계", "🔍 Starting fact-checking and critical review", "info")
        time.sleep(1)

        content = project.generated_content

        # Perform fact-checking
        add_log(db_engine, project_id, "3단계", "📚 Analyzing content for factual accuracy", "info")

        system_message = """You are an expert fact-checker and critical reviewer for medical/scientific books.

Your task is to:
1. Identify factual claims that need verification
2. Check for logical consistency
3. Flag any potentially misleading or incorrect information
4. Suggest improvements for accuracy and clarity
5. Provide critical feedback on the content quality"""

        user_message = f"""Review this book content for factual accuracy and quality.

Book Title: {project.name}
Subject: {project.book_idea}

Content to Review (first 3000 characters):
{content[:3000]}

Please provide:
1. Overall assessment of factual accuracy
2. Key facts that should be verified
3. Any logical inconsistencies or errors found
4. Suggestions for improvement
5. Critical feedback on content quality

Format your response as a structured report."""

        try:
            response = llm_client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,  # Lower temperature for more factual responses
                max_tokens=3000,
                top_p=0.9
            )

            review_content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens

            # Store review in a new field (for now, append to user_feedback)
            review_report = f"\n\n## Stage 3: Fact Check & Critical Review\n\n{review_content}"

            new_feedback = (project.user_feedback or "") + review_report
            new_tokens = (project.tokens_used or 0) + tokens_used

            # Use explicit SQL update for reliability with background threads
            from sqlalchemy import update
            db.execute(
                update(Project)
                .where(Project.id == project_id)
                .values(user_feedback=new_feedback, tokens_used=new_tokens)
            )
            db.commit()

            add_log(db_engine, project_id, "3단계",
                   f"✅ Fact-checking completed ({tokens_used} tokens)",
                   "success")
            time.sleep(1)

            # Mark stage as completed
            db.execute(update(Project).where(Project.id == project_id).values(stage_status="completed"))
            db.commit()

            add_log(db_engine, project_id, "3단계",
                   "🎉 Stage 3 (Fact Check & Review) completed!",
                   "success")

        except Exception as e:
            add_log(db_engine, project_id, "3단계",
                   f"❌ Error during review: {str(e)}",
                   "error")
            from sqlalchemy import update
            db.execute(update(Project).where(Project.id == project_id).values(stage_status="error"))
            db.commit()

    except Exception as e:
        add_log(db_engine, project_id, "3단계", f"❌ Fatal error: {str(e)}", "error")
        from sqlalchemy import update
        db.execute(update(Project).where(Project.id == project_id).values(stage_status="error"))
        db.commit()
    finally:
        db.close()

class ProgressLogResponse(BaseModel):
    id: int
    stage: str
    message: str
    level: str
    created_at: str

@app.get("/api/projects/{project_id}/logs", response_model=List[ProgressLogResponse])
async def get_project_logs(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """User: Get progress logs for own project"""
    # Verify user owns this project
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    logs = db.query(ProgressLog).filter(
        ProgressLog.project_id == project_id
    ).order_by(ProgressLog.created_at.asc()).all()

    return [
        ProgressLogResponse(
            id=log.id,
            stage=log.stage,
            message=log.message,
            level=log.level,
            created_at=log.created_at.isoformat()
        )
        for log in logs
    ]

@app.get("/api/admin/projects/{project_id}/logs", response_model=List[ProgressLogResponse])
async def admin_get_project_logs(
    project_id: int,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin: Get progress logs for a project"""
    logs = db.query(ProgressLog).filter(
        ProgressLog.project_id == project_id
    ).order_by(ProgressLog.created_at.asc()).all()

    return [
        ProgressLogResponse(
            id=log.id,
            stage=log.stage,
            message=log.message,
            level=log.level,
            created_at=log.created_at.isoformat()
        )
        for log in logs
    ]

class ChapterInfo(BaseModel):
    chapter_number: int
    title: str
    word_count: int

class GeneratedContentInfo(BaseModel):
    folder_location: str
    total_chapters: int
    total_words: int
    chapters: List[ChapterInfo]

@app.get("/api/projects/{project_id}/content-info", response_model=GeneratedContentInfo)
async def get_content_info(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get information about generated English content"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.generated_content:
        raise HTTPException(status_code=404, detail="No generated content found")

    # Parse chapters from generated_content
    import re
    content = project.generated_content

    # Split by chapter markers
    chapter_pattern = r'## Chapter (\d+): ([^\n]+)'
    chapter_matches = list(re.finditer(chapter_pattern, content))

    chapters = []
    total_words = len(content.split())

    for i, match in enumerate(chapter_matches):
        chapter_num = int(match.group(1))
        chapter_title = match.group(2).strip()

        # Get chapter content (from this match to next match or end)
        start_pos = match.start()
        end_pos = chapter_matches[i + 1].start() if i + 1 < len(chapter_matches) else len(content)
        chapter_content = content[start_pos:end_pos]
        word_count = len(chapter_content.split())

        chapters.append(ChapterInfo(
            chapter_number=chapter_num,
            title=chapter_title,
            word_count=word_count
        ))

    folder_location = f"/var/www/aibook/bookmaker/backend/generated/{project.user_id}/project_{project.id}"

    return GeneratedContentInfo(
        folder_location=folder_location,
        total_chapters=len(chapters),
        total_words=total_words,
        chapters=chapters
    )

@app.get("/api/projects/{project_id}/chapters/{chapter_number}")
async def get_chapter_html(
    project_id: int,
    chapter_number: int,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db)
):
    """Get a specific chapter as HTML for viewing

    Accepts authentication via either:
    1. Authorization header (preferred for API calls)
    2. token query parameter (for direct browser access)
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.generated_content:
        raise HTTPException(status_code=404, detail="No generated content found")

    # Extract the specific chapter
    import re
    content = project.generated_content

    chapter_pattern = r'## Chapter (\d+): ([^\n]+)'
    chapter_matches = list(re.finditer(chapter_pattern, content))

    chapter_found = None
    for i, match in enumerate(chapter_matches):
        if int(match.group(1)) == chapter_number:
            start_pos = match.start()
            end_pos = chapter_matches[i + 1].start() if i + 1 < len(chapter_matches) else len(content)
            chapter_content = content[start_pos:end_pos]
            chapter_title = match.group(2).strip()
            chapter_found = (chapter_title, chapter_content)
            break

    if not chapter_found:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_number} not found")

    chapter_title, chapter_content = chapter_found

    # Convert markdown to HTML with basic styling
    try:
        import markdown
        html_content = markdown.markdown(chapter_content, extensions=['fenced_code', 'tables'])
    except ImportError:
        # Fallback to simple pre-formatted text
        html_content = f"<pre>{chapter_content}</pre>"

    html_page = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Chapter {chapter_number}: {chapter_title}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 2rem;
                line-height: 1.6;
                color: #333;
                background: #f9f9f9;
            }}
            .container {{
                background: white;
                padding: 3rem;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h1, h2, h3 {{
                color: #2563eb;
                margin-top: 1.5em;
            }}
            h1 {{
                border-bottom: 3px solid #2563eb;
                padding-bottom: 0.5rem;
            }}
            code {{
                background: #f4f4f4;
                padding: 0.2em 0.4em;
                border-radius: 3px;
                font-size: 0.9em;
            }}
            pre {{
                background: #1e1e1e;
                color: #d4d4d4;
                padding: 1rem;
                border-radius: 6px;
                overflow-x: auto;
            }}
            pre code {{
                background: none;
                color: inherit;
            }}
            .meta {{
                color: #666;
                font-size: 0.9rem;
                margin-bottom: 2rem;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="meta">
                <strong>Book:</strong> {project.name}<br>
                <strong>Chapter {chapter_number}:</strong> {chapter_title}
            </div>
            {html_content}
        </div>
    </body>
    </html>
    """

    return Response(content=html_page, media_type="text/html")


@app.get("/api/projects/{project_id}/download-pdf")
async def download_project_pdf(
    project_id: int,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db)
):
    """Download the generated PDF for a project

    Accepts authentication via either:
    1. Authorization header (preferred for API calls)
    2. token query parameter (for direct browser access)
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # English PDF is available once Stage 4 completes (even if now on Stage 5)
    stage_num = int(project.stage[0])  # Extract number from "4단계" or "5단계"
    if stage_num < 4 or (stage_num == 4 and project.stage_status != "completed"):
        raise HTTPException(status_code=400, detail="PDF not yet generated. Please complete Stage 4.")

    # Find the PDF file
    output_dir = Path(f"/var/www/aibook/bookmaker/backend/output/user_{project.user_id}")

    # Sanitize project name (same logic as in generate_book_pdf)
    safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in project.name)
    safe_name = safe_name.strip().replace(' ', '_')[:50]
    if not safe_name:
        safe_name = f"book_{project.id}"

    pdf_file = output_dir / f"{safe_name}.pdf"

    if not pdf_file.exists():
        # Try to find any PDF for this project
        possible_pdfs = list(output_dir.glob("*.pdf")) if output_dir.exists() else []
        if possible_pdfs:
            pdf_file = possible_pdfs[0]
        else:
            raise HTTPException(status_code=404, detail="PDF file not found. Please regenerate.")

    # Use URL encoding for non-ASCII filenames (RFC 5987)
    from urllib.parse import quote
    ascii_filename = f"book_{project.id}.pdf"
    encoded_filename = quote(f"{project.name}.pdf")

    return FileResponse(
        pdf_file,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}",
            "Cache-Control": "no-cache"
        }
    )


@app.get("/api/projects/{project_id}/download-korean-pdf")
async def download_korean_pdf(
    project_id: int,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db)
):
    """Download the generated Korean PDF for a project

    Accepts authentication via either:
    1. Authorization header (preferred for API calls)
    2. token query parameter (for direct browser access)
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Korean PDF is available only when Stage 5 is completed
    if project.stage != "5단계" or project.stage_status != "completed":
        raise HTTPException(status_code=400, detail="Korean PDF not yet generated. Please complete Stage 5.")

    # Debug log for troubleshooting
    import logging
    logging.info(f"Korean PDF download: project={project.id}, stage={project.stage}, status={project.stage_status}")

    # Find the Korean PDF file
    output_dir = Path(f"/var/www/aibook/bookmaker/backend/output/user_{project.user_id}")

    # Sanitize project name (same logic as in translate_to_korean)
    safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in project.name)
    safe_name = safe_name.strip().replace(' ', '_')[:50]
    if not safe_name:
        safe_name = f"book_{project.id}"

    korean_pdf_file = output_dir / f"{safe_name}_KO.pdf"

    if not korean_pdf_file.exists():
        # Try to find any Korean PDF for this project
        possible_pdfs = list(output_dir.glob("*_KO.pdf")) if output_dir.exists() else []
        if possible_pdfs:
            korean_pdf_file = possible_pdfs[0]
        else:
            raise HTTPException(status_code=404, detail="Korean PDF file not found. Please regenerate.")

    # Use URL encoding for non-ASCII filenames (RFC 5987)
    from urllib.parse import quote
    ascii_filename = f"book_{project.id}_KO.pdf"
    encoded_filename = quote(f"{project.name}_한글.pdf")

    return FileResponse(
        korean_pdf_file,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}",
            "Cache-Control": "no-cache"
        }
    )


@app.get("/api/projects/{project_id}/download-markdown")
async def download_markdown(
    project_id: int,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db)
):
    """Download the English markdown file for a project"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Find the markdown file
    output_dir = Path(f"/var/www/aibook/bookmaker/backend/output/user_{project.user_id}")

    safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in project.name)
    safe_name = safe_name.strip().replace(' ', '_')[:50]
    if not safe_name:
        safe_name = f"book_{project.id}"

    md_file = output_dir / f"{safe_name}.md"

    if not md_file.exists():
        possible_mds = list(output_dir.glob("*.md")) if output_dir.exists() else []
        # Exclude Korean markdown
        possible_mds = [f for f in possible_mds if not f.name.endswith("_KO.md")]
        if possible_mds:
            md_file = possible_mds[0]
        else:
            raise HTTPException(status_code=404, detail="Markdown file not found.")

    # Use URL encoding for non-ASCII filenames (RFC 5987)
    from urllib.parse import quote
    ascii_filename = f"book_{project.id}.md"
    encoded_filename = quote(f"{project.name}.md")

    return FileResponse(
        md_file,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}",
            "Cache-Control": "no-cache"
        }
    )


@app.get("/api/projects/{project_id}/download-korean-markdown")
async def download_korean_markdown(
    project_id: int,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db)
):
    """Download the Korean markdown file for a project"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.stage != "5단계" or project.stage_status != "completed":
        raise HTTPException(status_code=400, detail="Korean translation not yet completed.")

    # Find the Korean markdown file
    output_dir = Path(f"/var/www/aibook/bookmaker/backend/output/user_{project.user_id}")

    safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in project.name)
    safe_name = safe_name.strip().replace(' ', '_')[:50]
    if not safe_name:
        safe_name = f"book_{project.id}"

    korean_md_file = output_dir / f"{safe_name}_KO.md"

    if not korean_md_file.exists():
        possible_mds = list(output_dir.glob("*_KO.md")) if output_dir.exists() else []
        if possible_mds:
            korean_md_file = possible_mds[0]
        else:
            raise HTTPException(status_code=404, detail="Korean markdown file not found.")

    # Use URL encoding for non-ASCII filenames (RFC 5987)
    from urllib.parse import quote
    ascii_filename = f"book_{project.id}_KO.md"
    encoded_filename = quote(f"{project.name}_한글.md")

    return FileResponse(
        korean_md_file,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}",
            "Cache-Control": "no-cache"
        }
    )


class PDFStatusResponse(BaseModel):
    has_pdf: bool
    pdf_path: Optional[str] = None
    pdf_size: Optional[int] = None
    has_korean_pdf: bool = False
    korean_pdf_path: Optional[str] = None
    korean_pdf_size: Optional[int] = None
    stage: str
    stage_status: str


@app.get("/api/projects/{project_id}/pdf-status", response_model=PDFStatusResponse)
async def get_pdf_status(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if PDF has been generated for a project"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Find the PDF file
    output_dir = Path(f"/var/www/aibook/bookmaker/backend/output/user_{project.user_id}")

    safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in project.name)
    safe_name = safe_name.strip().replace(' ', '_')[:50]
    if not safe_name:
        safe_name = f"book_{project.id}"

    pdf_file = output_dir / f"{safe_name}.pdf"
    korean_pdf_file = output_dir / f"{safe_name}_KO.pdf"

    response = PDFStatusResponse(
        has_pdf=pdf_file.exists(),
        pdf_path=str(pdf_file) if pdf_file.exists() else None,
        pdf_size=pdf_file.stat().st_size if pdf_file.exists() else None,
        has_korean_pdf=korean_pdf_file.exists(),
        korean_pdf_path=str(korean_pdf_file) if korean_pdf_file.exists() else None,
        korean_pdf_size=korean_pdf_file.stat().st_size if korean_pdf_file.exists() else None,
        stage=project.stage or "",
        stage_status=project.stage_status or ""
    )

    return response


@app.get("/api/admin/stats", response_model=DashboardStats)
async def admin_get_stats(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin: Get dashboard statistics"""
    from sqlalchemy import func

    total_users = db.query(func.count(User.id)).scalar()
    total_projects = db.query(func.count(Project.id)).scalar()
    total_prompts_generated = db.query(func.count(Project.id)).filter(Project.adapted_prompt.isnot(None)).scalar()
    total_tokens_used = db.query(func.coalesce(func.sum(Project.tokens_used), 0)).scalar()

    # Recent activity - last 10 projects updated
    recent = db.query(Project, User.username).join(User).order_by(Project.updated_at.desc()).limit(10).all()
    recent_activity = [
        {
            "project_name": p.Project.name,
            "username": p.username,
            "action": "generated" if p.Project.adapted_prompt else "created",
            "updated_at": p.Project.updated_at.isoformat()
        }
        for p in recent
    ]

    return DashboardStats(
        total_users=total_users,
        total_projects=total_projects,
        total_prompts_generated=total_prompts_generated,
        total_tokens_used=int(total_tokens_used),
        recent_activity=recent_activity
    )

# Health check

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "bookmaker",
        "version": "3.0.0",
        "groq_configured": bool(GROQ_API_KEY),
        "features": ["multi-user", "multi-project", "auth"]
    }

# Public: Published Books (accessible to all authenticated users)

@app.get("/api/books", response_model=List[BookGroup])
async def get_published_books(
    current_user: User = Depends(get_current_user)
):
    """Public: Get all published PDF books from /var/www/aibook/*/output folders"""
    import os
    from datetime import datetime

    base_path = Path("/var/www/aibook")
    book_groups = []

    if not base_path.exists():
        return []

    # Find all 'output' directories recursively
    output_dirs = []
    for root, dirs, files in os.walk(base_path):
        if 'output' in dirs:
            output_path = Path(root) / 'output'
            output_dirs.append(output_path)

    # Scan each output directory for PDF files
    for output_dir in output_dirs:
        pdf_files = list(output_dir.glob("*.pdf"))

        if pdf_files:
            # Get project name from parent directory
            project_name = output_dir.parent.name

            books = []
            for pdf_file in pdf_files:
                stat = pdf_file.stat()
                books.append(BookFile(
                    filename=pdf_file.name,
                    path=str(pdf_file),
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime).isoformat()
                ))

            book_groups.append(BookGroup(
                project_name=project_name,
                output_path=str(output_dir),
                books=sorted(books, key=lambda x: x.filename)
            ))

    return sorted(book_groups, key=lambda x: x.project_name)

@app.get("/api/books/view")
async def view_published_book(
    path: str,
    current_user: User = Depends(get_current_user_flexible)
):
    """Public: Serve PDF file for viewing

    Accepts authentication via either:
    1. Authorization header (preferred for API calls)
    2. token query parameter (for direct browser access)
    """
    pdf_path = Path(path)

    # Security check: ensure path is within /var/www/aibook
    base_path = Path("/var/www/aibook")
    try:
        pdf_path.resolve().relative_to(base_path.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if file exists and is a PDF
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")

    if pdf_path.suffix.lower() != '.pdf':
        raise HTTPException(status_code=400, detail="Not a PDF file")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
        headers={
            "Content-Disposition": f"inline; filename={pdf_path.name}",
            "Cache-Control": "public, max-age=3600"
        }
    )

# Admin: Generated Books Management

@app.get("/api/admin/books", response_model=List[BookGroup])
async def admin_get_books(
    admin_user: User = Depends(get_admin_user)
):
    """Admin: Scan for generated PDF books in /var/www/aibook/*/output folders"""
    import os
    from datetime import datetime

    base_path = Path("/var/www/aibook")
    book_groups = []

    if not base_path.exists():
        return []

    # Find all 'output' directories recursively
    output_dirs = []
    for root, dirs, files in os.walk(base_path):
        if 'output' in dirs:
            output_path = Path(root) / 'output'
            output_dirs.append(output_path)

    # Scan each output directory for PDF files
    for output_dir in output_dirs:
        pdf_files = list(output_dir.glob("*.pdf"))

        if pdf_files:
            # Get project name from parent directory
            project_name = output_dir.parent.name

            books = []
            for pdf_file in pdf_files:
                stat = pdf_file.stat()
                books.append(BookFile(
                    filename=pdf_file.name,
                    path=str(pdf_file),
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime).isoformat()
                ))

            book_groups.append(BookGroup(
                project_name=project_name,
                output_path=str(output_dir),
                books=sorted(books, key=lambda x: x.filename)
            ))

    return sorted(book_groups, key=lambda x: x.project_name)

@app.get("/api/admin/books/view")
async def admin_view_book(
    path: str,
    current_user: User = Depends(get_current_user_flexible)
):
    """Admin: Serve PDF file for viewing

    Accepts authentication via either:
    1. Authorization header (preferred for API calls)
    2. token query parameter (for direct browser access)
    """
    # Verify admin access
    if current_user.username != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    pdf_path = Path(path)

    # Security check: ensure path is within /var/www/aibook
    base_path = Path("/var/www/aibook")
    try:
        pdf_path.resolve().relative_to(base_path.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if file exists and is a PDF
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")

    if pdf_path.suffix.lower() != '.pdf':
        raise HTTPException(status_code=400, detail="Not a PDF file")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
        headers={
            "Content-Disposition": f"inline; filename={pdf_path.name}",
            "Cache-Control": "public, max-age=3600"
        }
    )


# ====================
# Voice Files Endpoints
# ====================

VOICE_FILES_DIR = Path(__file__).parent / "voice_files"

# Allowed extensions for voice/audio files
ALLOWED_AUDIO_EXTENSIONS = {'.wav', '.mp4', '.m4a', '.mp3', '.ogg', '.webm'}


class VoiceFileInfo(BaseModel):
    filename: str
    path: str
    size: int
    modified: str
    duration: Optional[float] = None


@app.get("/api/voice-files", response_model=List[VoiceFileInfo])
async def list_voice_files(
    current_user: User = Depends(get_current_user)
):
    """List all voice files for the current user."""
    user_voice_dir = VOICE_FILES_DIR / f"user_{current_user.id}"

    if not user_voice_dir.exists():
        return []

    files = []
    for f in user_voice_dir.iterdir():
        if f.is_file() and f.suffix.lower() in ALLOWED_AUDIO_EXTENSIONS:
            stat = f.stat()
            files.append(VoiceFileInfo(
                filename=f.name,
                path=str(f),
                size=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime).isoformat()
            ))

    # Sort by modified time, newest first
    files.sort(key=lambda x: x.modified, reverse=True)
    return files


@app.post("/api/voice-files/upload")
async def upload_voice_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload a voice/audio file."""
    # Validate file extension
    ext = Path(file.filename).suffix.lower() if file.filename else ''
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}"
        )

    # Create user directory if needed
    user_voice_dir = VOICE_FILES_DIR / f"user_{current_user.id}"
    user_voice_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    safe_filename = file.filename.replace('/', '_').replace('\\', '_')
    file_path = user_voice_dir / safe_filename

    # Handle duplicate filenames
    counter = 1
    original_stem = file_path.stem
    while file_path.exists():
        file_path = user_voice_dir / f"{original_stem}_{counter}{ext}"
        counter += 1

    content = await file.read()
    file_path.write_bytes(content)

    stat = file_path.stat()
    return {
        "success": True,
        "filename": file_path.name,
        "path": str(file_path),
        "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
    }


@app.delete("/api/voice-files/{filename}")
async def delete_voice_file(
    filename: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a voice file."""
    user_voice_dir = VOICE_FILES_DIR / f"user_{current_user.id}"
    file_path = user_voice_dir / filename

    # Security check
    try:
        file_path.resolve().relative_to(user_voice_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    file_path.unlink()
    return {"success": True, "message": f"Deleted {filename}"}


@app.get("/api/voice-files/{filename}")
async def get_voice_file(
    filename: str,
    current_user: User = Depends(get_current_user_flexible)
):
    """Stream a voice file for playback."""
    user_voice_dir = VOICE_FILES_DIR / f"user_{current_user.id}"
    file_path = user_voice_dir / filename

    # Security check
    try:
        file_path.resolve().relative_to(user_voice_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    ext = file_path.suffix.lower()
    media_types = {
        '.wav': 'audio/wav',
        '.mp3': 'audio/mpeg',
        '.mp4': 'video/mp4',
        '.m4a': 'audio/mp4',
        '.ogg': 'audio/ogg',
        '.webm': 'video/webm'
    }
    media_type = media_types.get(ext, 'application/octet-stream')

    return FileResponse(
        file_path,
        media_type=media_type,
        filename=filename
    )


# Serve static frontend files in production
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/")
    async def serve_frontend():
        """Serve the frontend index.html."""
        index_path = frontend_dist / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="Frontend not built")
        return FileResponse(index_path)

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve SPA for all non-API routes."""
        if full_path.startswith("api/") or full_path.startswith("health"):
            raise HTTPException(status_code=404, detail="Endpoint not found")

        index_path = frontend_dist / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="Frontend not built")
        return FileResponse(index_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8086,
        reload=True
    )
