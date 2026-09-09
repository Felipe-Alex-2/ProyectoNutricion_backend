from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.recipe import Recipe, RecipeAssignment
from app.models.activity_log import ActivityLog
from app.schemas.recipe import RecipeCreate, RecipeUpdate, RecipeResponse

router = APIRouter(prefix="/recipes", tags=["Recetas"])


def _recipe_to_response(recipe: Recipe) -> RecipeResponse:
    assigned_ids = [a.patient_id for a in recipe.assignments] if recipe.assignments else []
    data = RecipeResponse.model_validate(recipe)
    data.assigned_patient_ids = assigned_ids
    return data


@router.get("/my-plan", response_model=List[RecipeResponse])
def get_my_plan_recipes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtiene las recetas del plan alimenticio asignadas al paciente actual (para la App Móvil)."""
    # 1. Recetas específicamente asignadas a este paciente
    assigned_recipe_ids = (
        db.query(RecipeAssignment.recipe_id)
        .filter(RecipeAssignment.patient_id == current_user.id)
        .all()
    )
    target_ids = [r[0] for r in assigned_recipe_ids]

    # 2. Consultar recetas activas asignadas o de la clínica si no hay específicas
    if target_ids:
        recipes = (
            db.query(Recipe)
            .filter(Recipe.id.in_(target_ids), Recipe.is_active == True)
            .order_by(Recipe.created_at.desc())
            .all()
        )
    else:
        recipes = []

    return [_recipe_to_response(r) for r in recipes]


@router.get("", response_model=List[RecipeResponse])
def list_recipes(
    category: Optional[str] = Query(None, description="Filtrar por categoría"),
    difficulty: Optional[str] = Query(None, description="Filtrar por dificultad"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista las recetas disponibles (activas) con sus pacientes asignados."""
    query = db.query(Recipe).filter(Recipe.is_active == True)

    # Filtrar por tenant si el usuario no es ADMIN_SAAS y la receta tiene tenant_id
    if current_user.role_id != "ADMIN_SAAS" and current_user.tenant_id:
        query = query.filter(
            (Recipe.tenant_id == current_user.tenant_id) | (Recipe.tenant_id == None)
        )

    if category:
        query = query.filter(Recipe.category == category)
    if difficulty:
        query = query.filter(Recipe.difficulty == difficulty)

    recipes = query.order_by(Recipe.created_at.desc()).all()
    return [_recipe_to_response(r) for r in recipes]


@router.post("", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
def create_recipe(
    data: RecipeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crear una nueva receta en la plataforma Web y asignarla a uno o más pacientes."""
    if current_user.role_id not in ["ADMIN_SAAS", "ADMIN_ORGANIZATION", "NUTRICIONISTA"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para crear recetas culinarias.",
        )

    tenant_id = current_user.tenant_id if current_user.role_id != "ADMIN_SAAS" else (data.tenant_id or current_user.tenant_id)

    recipe = Recipe(
        tenant_id=tenant_id,
        created_by=current_user.id,
        title=data.title,
        description=data.description,
        image_url=data.image_url,
        calories=data.calories,
        protein=data.protein,
        carbohydrates=data.carbohydrates,
        fats=data.fats,
        fiber=data.fiber,
        sodium=data.sodium,
        servings=data.servings,
        prep_time_minutes=data.prep_time_minutes,
        cook_time_minutes=data.cook_time_minutes,
        difficulty=data.difficulty,
        category=data.category,
        ingredients=data.ingredients,
        instructions=data.instructions,
    )
    db.add(recipe)
    db.flush()

    # Asignar a los pacientes seleccionados
    if data.assigned_patient_ids:
        for p_id in data.assigned_patient_ids:
            db.add(RecipeAssignment(recipe_id=recipe.id, patient_id=p_id))

    # Log de actividad
    log = ActivityLog(
        user_id=current_user.id,
        user_email=current_user.email,
        user_name=current_user.full_name,
        action="RECETA_CREADA",
        description=f"Se creó la receta '{data.title}' con {data.calories} kcal y {len(data.assigned_patient_ids or [])} paciente(s) asignado(s).",
        category="CLINICAL",
    )
    db.add(log)
    db.commit()
    db.refresh(recipe)
    return _recipe_to_response(recipe)


@router.get("/{recipe_id}", response_model=RecipeResponse)
def get_recipe(
    recipe_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtener el detalle de una receta con sus pacientes asignados."""
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.is_active == True).first()
    if not recipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receta no encontrada.")
    return _recipe_to_response(recipe)


@router.put("/{recipe_id}", response_model=RecipeResponse)
def update_recipe(
    recipe_id: str,
    data: RecipeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Actualizar datos de una receta y sus asignaciones a pacientes."""
    if current_user.role_id not in ["ADMIN_SAAS", "ADMIN_ORGANIZATION", "NUTRICIONISTA"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado.")

    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receta no encontrada.")

    if current_user.role_id == "NUTRICIONISTA" and recipe.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo puedes modificar tus recetas.")

    update_data = data.model_dump(exclude_unset=True, exclude={"assigned_patient_ids"})
    for key, value in update_data.items():
        setattr(recipe, key, value)

    # Actualizar asignaciones si vienen en el payload
    if data.assigned_patient_ids is not None:
        db.query(RecipeAssignment).filter(RecipeAssignment.recipe_id == recipe.id).delete(synchronize_session="fetch")
        for p_id in data.assigned_patient_ids:
            db.add(RecipeAssignment(recipe_id=recipe.id, patient_id=p_id))
        db.flush()
        db.expire(recipe, ["assignments"])

    log = ActivityLog(
        user_id=current_user.id,
        user_email=current_user.email,
        user_name=current_user.full_name,
        action="RECETA_ACTUALIZADA",
        description=f"Se actualizó la receta '{recipe.title}'.",
        category="CLINICAL",
    )
    db.add(log)
    db.commit()
    db.refresh(recipe)
    return _recipe_to_response(recipe)


@router.delete("/{recipe_id}", status_code=status.HTTP_200_OK)
def delete_recipe(
    recipe_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Desactivar/eliminar una receta."""
    if current_user.role_id not in ["ADMIN_SAAS", "ADMIN_ORGANIZATION", "NUTRICIONISTA"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado.")

    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receta no encontrada.")

    if current_user.role_id == "NUTRICIONISTA" and recipe.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes eliminar recetas de otros especialistas.")

    recipe.is_active = False
    log = ActivityLog(
        user_id=current_user.id,
        user_email=current_user.email,
        user_name=current_user.full_name,
        action="RECETA_ELIMINADA",
        description=f"Se eliminó la receta '{recipe.title}'.",
        category="CLINICAL",
    )
    db.add(log)
    db.commit()
    return {"message": "Receta eliminada exitosamente."}
