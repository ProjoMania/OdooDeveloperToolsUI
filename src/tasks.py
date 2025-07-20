"""
Task Management Blueprint
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
import logging
from datetime import datetime
from typing import Optional
from .models import Task, TaskNote, Project, db

tasks_bp = Blueprint('tasks', __name__, url_prefix='/tasks')
logger = logging.getLogger(__name__)

@tasks_bp.route('/')
def tasks():
    """Display list of tasks"""
    try:
        tasks_list = Task.query.order_by(Task.created_at.desc()).all()
        return render_template('tasks/index.html', tasks=tasks_list)
    except Exception as e:
        logger.error(f"Error fetching tasks: {str(e)}")
        flash('Error loading tasks', 'danger')
        return render_template('tasks/index.html', tasks=[])

@tasks_bp.route('/new')
def new_task():
    """Display form to create new task"""
    try:
        projects = Project.query.filter_by(status='active').all()
        return render_template('tasks/form.html', task=None, projects=projects)
    except Exception as e:
        logger.error(f"Error loading projects for task creation: {str(e)}")
        flash('Error loading projects', 'danger')
        return redirect(url_for('tasks.tasks'))

@tasks_bp.route('/new', methods=['POST'])
def create_task():
    """Handle task creation"""
    try:
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        status = request.form.get('status', 'todo')
        priority = request.form.get('priority', 'medium')
        project_id = request.form.get('project_id', '').strip()
        due_date_str = request.form.get('due_date', '').strip()
        
        # Validation
        if not title:
            flash('Task title is required', 'danger')
            return redirect(url_for('tasks.new_task'))
        
        if not project_id:
            flash('Project is required', 'danger')
            return redirect(url_for('tasks.new_task'))
        
        # Validate project exists
        project = Project.query.get(project_id)
        if not project:
            flash('Selected project does not exist', 'danger')
            return redirect(url_for('tasks.new_task'))
        
        # Parse due date
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d %H:%M')
            except ValueError:
                flash('Invalid due date format', 'danger')
                return redirect(url_for('tasks.new_task'))
        
        # Create task
        task = Task(
            title=title,
            description=description,
            status=status,
            priority=priority,
            project_id=project_id,
            due_date=due_date
        )
        
        db.session.add(task)
        db.session.commit()
        
        flash(f'Task "{title}" created successfully', 'success')
        return redirect(url_for('tasks.tasks'))
        
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        db.session.rollback()
        flash(f'Error creating task: {str(e)}', 'danger')
        return redirect(url_for('tasks.new_task'))

@tasks_bp.route('/<int:task_id>')
def view_task(task_id):
    """Display task details"""
    try:
        task = Task.query.get_or_404(task_id)
        return render_template('tasks/view.html', task=task)
    except Exception as e:
        logger.error(f"Error viewing task {task_id}: {str(e)}")
        flash('Error loading task', 'danger')
        return redirect(url_for('tasks.tasks'))

@tasks_bp.route('/<int:task_id>/edit')
def edit_task(task_id):
    """Display task edit form"""
    try:
        task = Task.query.get_or_404(task_id)
        projects = Project.query.filter_by(status='active').all()
        return render_template('tasks/form.html', task=task, projects=projects)
    except Exception as e:
        logger.error(f"Error editing task {task_id}: {str(e)}")
        flash('Error loading task', 'danger')
        return redirect(url_for('tasks.tasks'))

@tasks_bp.route('/<int:task_id>/edit', methods=['POST'])
def update_task(task_id):
    """Handle task update"""
    try:
        task = Task.query.get_or_404(task_id)
        
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        status = request.form.get('status', 'todo')
        priority = request.form.get('priority', 'medium')
        project_id = request.form.get('project_id', '').strip()
        due_date_str = request.form.get('due_date', '').strip()
        
        # Validation
        if not title:
            flash('Task title is required', 'danger')
            return redirect(url_for('tasks.edit_task', task_id=task_id))
        
        if not project_id:
            flash('Project is required', 'danger')
            return redirect(url_for('tasks.edit_task', task_id=task_id))
        
        # Validate project exists
        project = Project.query.get(project_id)
        if not project:
            flash('Selected project does not exist', 'danger')
            return redirect(url_for('tasks.edit_task', task_id=task_id))
        
        # Parse due date
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d %H:%M')
            except ValueError:
                flash('Invalid due date format', 'danger')
                return redirect(url_for('tasks.edit_task', task_id=task_id))
        
        # Update task
        task.title = title
        task.description = description
        task.status = status
        task.priority = priority
        task.project_id = project_id
        task.due_date = due_date
        task.updated_at = datetime.utcnow()
        
        # Mark as completed if status is done
        if status == 'done' and not task.completed_at:
            task.completed_at = datetime.utcnow()
        elif status != 'done':
            task.completed_at = None
        
        db.session.commit()
        
        flash(f'Task "{title}" updated successfully', 'success')
        return redirect(url_for('tasks.view_task', task_id=task_id))
        
    except Exception as e:
        logger.error(f"Error updating task {task_id}: {str(e)}")
        db.session.rollback()
        flash(f'Error updating task: {str(e)}', 'danger')
        return redirect(url_for('tasks.edit_task', task_id=task_id))

@tasks_bp.route('/<int:task_id>/delete')
def delete_task_page(task_id):
    """Display task deletion confirmation"""
    try:
        task = Task.query.get_or_404(task_id)
        return render_template('tasks/delete_task.html', task=task)
    except Exception as e:
        logger.error(f"Error loading task for deletion {task_id}: {str(e)}")
        flash('Error loading task', 'danger')
        return redirect(url_for('tasks.tasks'))

@tasks_bp.route('/<int:task_id>/delete', methods=['POST'])
def delete_task(task_id):
    """Handle task deletion"""
    try:
        task = Task.query.get_or_404(task_id)
        task_title = task.title
        
        # Delete associated data (cascade will handle this)
        db.session.delete(task)
        db.session.commit()
        
        flash(f'Task "{task_title}" deleted successfully', 'success')
        return redirect(url_for('tasks.tasks'))
        
    except Exception as e:
        logger.error(f"Error deleting task {task_id}: {str(e)}")
        db.session.rollback()
        flash(f'Error deleting task: {str(e)}', 'danger')
        return redirect(url_for('tasks.tasks'))

@tasks_bp.route('/<int:task_id>/add_note', methods=['POST'])
def add_task_note(task_id):
    """Add note to task"""
    try:
        task = Task.query.get_or_404(task_id)
        
        content = request.form.get('content', '').strip()
        
        if not content:
            flash('Note content is required', 'danger')
            return redirect(url_for('tasks.view_task', task_id=task_id))
        
        # Add note to task
        note = TaskNote(
            task_id=task_id,
            content=content
        )
        
        db.session.add(note)
        db.session.commit()
        
        flash('Note added successfully', 'success')
        return redirect(url_for('tasks.view_task', task_id=task_id))
        
    except Exception as e:
        logger.error(f"Error adding note to task {task_id}: {str(e)}")
        db.session.rollback()
        flash(f'Error adding note: {str(e)}', 'danger')
        return redirect(url_for('tasks.view_task', task_id=task_id))

@tasks_bp.route('/<int:task_id>/toggle_status', methods=['POST'])
def toggle_task_status(task_id):
    """Toggle task completion status"""
    try:
        task = Task.query.get_or_404(task_id)
        
        if task.status == 'done':
            task.status = 'todo'
            task.completed_at = None
            flash(f'Task "{task.title}" marked as incomplete', 'info')
        else:
            task.status = 'done'
            task.completed_at = datetime.utcnow()
            flash(f'Task "{task.title}" marked as complete', 'success')
        
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        return redirect(url_for('tasks.view_task', task_id=task_id))
        
    except Exception as e:
        logger.error(f"Error toggling task status {task_id}: {str(e)}")
        db.session.rollback()
        flash(f'Error updating task status: {str(e)}', 'danger')
        return redirect(url_for('tasks.view_task', task_id=task_id)) 