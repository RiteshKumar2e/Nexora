"""REST endpoints for training the native model and tracking metrics."""
from __future__ import annotations

import asyncio
import os
import psutil
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from torch.utils.data import DataLoader

from app.auth.routes import get_current_user_optional
from nexora_model.config import CPU_SMALL
from nexora_model.dataset import InstructionDataset, load_instruction_data
from nexora_model.tokenizer import NexoraTokenizer
from nexora_model.transformer import NexoraTransformer
from nexora_model.training import NexoraTrainer

router = APIRouter(prefix="/training", tags=["training"])


# ── Global Training State ─────────────────────────────────────

class ActiveTrainingStatus:
    def __init__(self):
        self.is_running = False
        self.step = 0
        self.max_steps = 0
        self.epoch = 0.0
        self.train_loss = 0.0
        self.val_loss = 0.0
        self.lr = 0.0
        self.tokens_per_sec = 0.0
        self.steps_per_sec = 0.0
        self.elapsed_sec = 0.0
        self.trainer = None

active_status = ActiveTrainingStatus()


# ── Schemas ──────────────────────────────────────────────────

class StartTrainingRequest(BaseModel):
    max_steps: int = 50
    learning_rate: float = 3e-4


class TrainingStatusResponse(BaseModel):
    is_running: bool
    step: int
    max_steps: int
    epoch: float
    train_loss: float
    val_loss: float
    lr: float
    tokens_per_sec: float
    steps_per_sec: float
    elapsed_sec: float
    cpu_percent: float
    ram_percent: float


# ── Helper for async training execution ──────────────────────

def run_training_task(max_steps: int, lr: float):
    active_status.is_running = True
    active_status.max_steps = max_steps
    
    # 1. Setup small CPU config for speed/sandbox safety
    config = CPU_SMALL
    config.max_steps = max_steps
    config.learning_rate = lr
    config.eval_interval = max(10, max_steps // 5)
    config.save_interval = max_steps
    
    # 2. Build directories
    model_dir = "backend/nexora_model"
    os.makedirs(f"{model_dir}/checkpoints", exist_ok=True)
    
    # 3. Load dataset
    try:
        train_data, val_data, _, _ = load_instruction_data(f"{model_dir}/datasets/instructions.jsonl")
        tokenizer = NexoraTokenizer.load(f"{model_dir}/checkpoints/tokenizer.json")
    except Exception:
        # Fallback if tokenizer JSON not created yet
        sample_texts = ["Hello! I am Nexora.", "Write Python math tools here."]
        tokenizer = NexoraTokenizer.train(sample_texts)
        tokenizer.save(f"{model_dir}/checkpoints/tokenizer.json")
        train_data, val_data, _, _ = load_instruction_data(f"{model_dir}/datasets/instructions.jsonl")
        
    config.vocab_size = tokenizer.vocab_size
    model = NexoraTransformer(config)
    
    train_ds = InstructionDataset(train_data, tokenizer, max_len=config.max_seq_len)
    val_ds = InstructionDataset(val_data, tokenizer, max_len=config.max_seq_len)
    
    train_loader = DataLoader(train_ds, batch_size=config.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=config.batch_size)
    
    # 4. Callback to update global status variables
    def update_metrics(m):
        active_status.step = m.step
        active_status.epoch = m.epoch
        active_status.train_loss = m.train_loss
        if m.val_loss is not None:
            active_status.val_loss = m.val_loss
        active_status.lr = m.learning_rate
        active_status.tokens_per_sec = m.tokens_per_sec
        active_status.steps_per_sec = m.steps_per_sec
        active_status.elapsed_sec = m.elapsed_sec

    trainer = NexoraTrainer(
        model=model,
        config=config,
        train_loader=train_loader,
        val_loader=val_loader,
        output_dir=f"{model_dir}/checkpoints",
        log_callback=update_metrics
    )
    
    active_status.trainer = trainer
    
    # Run training blocking on background thread
    try:
        trainer.train()
    finally:
        active_status.is_running = False


# ── Routes ───────────────────────────────────────────────────

@router.post("/start")
async def start_training(
    body: StartTrainingRequest,
    background_tasks: BackgroundTasks,
    user = Depends(get_current_user_optional),
):
    if active_status.is_running:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Training is already running"
        )
        
    background_tasks.add_task(run_training_task, body.max_steps, body.learning_rate)
    return {"message": "Training started in background"}


@router.post("/stop")
async def stop_training(user = Depends(get_current_user_optional)):
    if not active_status.is_running or not active_status.trainer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No training task currently running"
        )
        
    active_status.trainer.stop()
    return {"message": "Stop signal sent to trainer"}


@router.get("/status", response_model=TrainingStatusResponse)
async def get_training_status():
    # Fetch resource specs
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    
    return TrainingStatusResponse(
        is_running=active_status.is_running,
        step=active_status.step,
        max_steps=active_status.max_steps,
        epoch=active_status.epoch,
        train_loss=active_status.train_loss,
        val_loss=active_status.val_loss,
        lr=active_status.lr,
        tokens_per_sec=active_status.tokens_per_sec,
        steps_per_sec=active_status.steps_per_sec,
        elapsed_sec=active_status.elapsed_sec,
        cpu_percent=cpu,
        ram_percent=ram
    )
