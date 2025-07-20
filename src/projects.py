"""
Project Management Blueprint
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
import logging
from datetime import datetime
from typing import Optional
from .models import Project, ProjectServer, ProjectDatabase, db

projects_bp = Blueprint('projects', __name__, url_prefix='/projects')
logger = logging.getLogger(__name__)

@projects_bp.route('/')
def projects():
    """Display list of projects"""
    try:
        projects_list = Project.query.order_by(Project.created_at.desc()).all()
        return render_template('projects/index.html', projects=projects_list)
    except Exception as e:
        logger.error(f"Error fetching projects: {str(e)}")
        flash('Error loading projects', 'danger')
        return render_template('projects/index.html', projects=[])

@projects_bp.route('/new')
def new_project():
    """Display form to create new project"""
    return render_template('projects/form.html', project=None)

@projects_bp.route('/new', methods=['POST'])
def create_project():
    """Handle project creation"""
    try:
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        status = request.form.get('status', 'active')
        repository_url = request.form.get('repository_url', '').strip()
        start_date_str = request.form.get('start_date', '').strip()
        end_date_str = request.form.get('end_date', '').strip()
        
        # Validation
        if not name:
            flash('Project name is required', 'danger')
            return redirect(url_for('projects.new_project'))
        
        # Parse dates
        start_date = None
        end_date = None
        
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid start date format', 'danger')
                return redirect(url_for('projects.new_project'))
        
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid end date format', 'danger')
                return redirect(url_for('projects.new_project'))
        
        # Create project
        project = Project(
            name=name,
            description=description,
            status=status,
            repository_url=repository_url,
            start_date=start_date,
            end_date=end_date
        )
        
        db.session.add(project)
        db.session.commit()
        
        flash(f'Project "{name}" created successfully', 'success')
        return redirect(url_for('projects.projects'))
        
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}")
        db.session.rollback()
        flash(f'Error creating project: {str(e)}', 'danger')
        return redirect(url_for('projects.new_project'))

@projects_bp.route('/<int:project_id>')
def view_project(project_id):
    """Display project details"""
    try:
        project = Project.query.get_or_404(project_id)
        return render_template('projects/view.html', project=project)
    except Exception as e:
        logger.error(f"Error viewing project {project_id}: {str(e)}")
        flash('Error loading project', 'danger')
        return redirect(url_for('projects.projects'))

@projects_bp.route('/<int:project_id>/edit')
def edit_project(project_id):
    """Display project edit form"""
    try:
        project = Project.query.get_or_404(project_id)
        return render_template('projects/form.html', project=project)
    except Exception as e:
        logger.error(f"Error editing project {project_id}: {str(e)}")
        flash('Error loading project', 'danger')
        return redirect(url_for('projects.projects'))

@projects_bp.route('/<int:project_id>/edit', methods=['POST'])
def update_project(project_id):
    """Handle project update"""
    try:
        project = Project.query.get_or_404(project_id)
        
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        status = request.form.get('status', 'active')
        repository_url = request.form.get('repository_url', '').strip()
        start_date_str = request.form.get('start_date', '').strip()
        end_date_str = request.form.get('end_date', '').strip()
        
        # Validation
        if not name:
            flash('Project name is required', 'danger')
            return redirect(url_for('projects.edit_project', project_id=project_id))
        
        # Parse dates
        start_date = None
        end_date = None
        
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid start date format', 'danger')
                return redirect(url_for('projects.edit_project', project_id=project_id))
        
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid end date format', 'danger')
                return redirect(url_for('projects.edit_project', project_id=project_id))
        
        # Update project
        project.name = name
        project.description = description
        project.status = status
        project.repository_url = repository_url
        project.start_date = start_date
        project.end_date = end_date
        project.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash(f'Project "{name}" updated successfully', 'success')
        return redirect(url_for('projects.view_project', project_id=project_id))
        
    except Exception as e:
        logger.error(f"Error updating project {project_id}: {str(e)}")
        db.session.rollback()
        flash(f'Error updating project: {str(e)}', 'danger')
        return redirect(url_for('projects.edit_project', project_id=project_id))

@projects_bp.route('/<int:project_id>/delete')
def delete_project_page(project_id):
    """Display project deletion confirmation"""
    try:
        project = Project.query.get_or_404(project_id)
        return render_template('projects/delete_project.html', project=project)
    except Exception as e:
        logger.error(f"Error loading project for deletion {project_id}: {str(e)}")
        flash('Error loading project', 'danger')
        return redirect(url_for('projects.projects'))

@projects_bp.route('/<int:project_id>/delete', methods=['POST'])
def delete_project(project_id):
    """Handle project deletion"""
    try:
        project = Project.query.get_or_404(project_id)
        project_name = project.name
        
        # Delete associated data (cascade will handle this)
        db.session.delete(project)
        db.session.commit()
        
        flash(f'Project "{project_name}" deleted successfully', 'success')
        return redirect(url_for('projects.projects'))
        
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {str(e)}")
        db.session.rollback()
        flash(f'Error deleting project: {str(e)}', 'danger')
        return redirect(url_for('projects.projects'))

@projects_bp.route('/<int:project_id>/add_server', methods=['POST'])
def add_project_server(project_id):
    """Add server to project"""
    try:
        project = Project.query.get_or_404(project_id)
        
        server_name = request.form.get('server_name', '').strip()
        server_role = request.form.get('server_role', '').strip()
        
        if not server_name:
            flash('Server name is required', 'danger')
            return redirect(url_for('projects.view_project', project_id=project_id))
        
        # Check if server already exists for this project
        existing_server = ProjectServer.query.filter_by(
            project_id=project_id, 
            server_name=server_name
        ).first()
        
        if existing_server:
            flash(f'Server "{server_name}" already exists for this project', 'warning')
            return redirect(url_for('projects.view_project', project_id=project_id))
        
        # Add server to project
        project_server = ProjectServer(
            project_id=project_id,
            server_name=server_name,
            server_role=server_role
        )
        
        db.session.add(project_server)
        db.session.commit()
        
        flash(f'Server "{server_name}" added to project successfully', 'success')
        return redirect(url_for('projects.view_project', project_id=project_id))
        
    except Exception as e:
        logger.error(f"Error adding server to project {project_id}: {str(e)}")
        db.session.rollback()
        flash(f'Error adding server to project: {str(e)}', 'danger')
        return redirect(url_for('projects.view_project', project_id=project_id))

@projects_bp.route('/<int:project_id>/add_database', methods=['POST'])
def add_project_database(project_id):
    """Add database to project"""
    try:
        project = Project.query.get_or_404(project_id)
        
        database_name = request.form.get('database_name', '').strip()
        database_type = request.form.get('database_type', '').strip()
        
        if not database_name:
            flash('Database name is required', 'danger')
            return redirect(url_for('projects.view_project', project_id=project_id))
        
        # Check if database already exists for this project
        existing_database = ProjectDatabase.query.filter_by(
            project_id=project_id, 
            database_name=database_name
        ).first()
        
        if existing_database:
            flash(f'Database "{database_name}" already exists for this project', 'warning')
            return redirect(url_for('projects.view_project', project_id=project_id))
        
        # Add database to project
        project_database = ProjectDatabase(
            project_id=project_id,
            database_name=database_name,
            database_type=database_type
        )
        
        db.session.add(project_database)
        db.session.commit()
        
        flash(f'Database "{database_name}" added to project successfully', 'success')
        return redirect(url_for('projects.view_project', project_id=project_id))
        
    except Exception as e:
        logger.error(f"Error adding database to project {project_id}: {str(e)}")
        db.session.rollback()
        flash(f'Error adding database to project: {str(e)}', 'danger')
        return redirect(url_for('projects.view_project', project_id=project_id)) 