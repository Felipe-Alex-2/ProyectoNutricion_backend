from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.recipe import Recipe
from app.models.activity_log import ActivityLog
from app.schemas.recipe import RecipeCreate, RecipeUpdate, RecipeResponse

router = APIRouter(prefix="/recipes", tags=["Recetas"])


@router.get("", response_model=List[RecipeResponse])
def list_recipes(
    category: Optional[str] = Query(None, description="Filtrar por categoría"),
    difficulty: Optional[str] = Query(None, description="Filtrar por dificultad"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista las recetas disponibles (activas)."""
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

    return query.order_by(Recipe.created_at.desc()).all()


@router.post("", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
def create_recipe(
    data: RecipeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crear una nueva receta en la plataforma Web (Nutricionistas y Administradores)."""
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

    # Log de actividad
    log = ActivityLog(
        user_id=current_user.id,
        user_email=current_user.email,
        user_name=current_user.full_name,
        action="RECETA_CREADA",
        description=f"Se creó la receta '{data.title}' con {data.calories} kcal.",
        category="CLINICAL",
    )
    db.add(log)
    db.commit()
    db.refresh(recipe)
    return recipe


@router.get("/{recipe_id}", response_model=RecipeResponse)
def get_recipe(
    recipe_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtener el detalle de una receta."""
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.is_active == True).first()
    if not recipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receta no encontrada.")
    return recipe


@router.put("/{recipe_id}", response_model=RecipeResponse)
def update_recipe(
    recipe_id: str,
    data: RecipeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Actualizar datos de una receta."""
    if current_user.role_id not in ["ADMIN_SAAS", "ADMIN_ORGANIZATION", "NUTRICIONISTA"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado.")

    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receta no encontrada.")

    # Validar que si es NUTRICIONISTA solo pueda editar sus propias recetas o de su clínica
    if current_user.role_id == "NUTRICIONISTA" and recipe.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo puedes modificar tus recetas.")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(recipe, key, value)

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
    return recipe


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
