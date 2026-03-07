from pydantic import BaseModel

class ModuleAccessBase(BaseModel):
    module_name: str
    free_access: bool = False
    starter_access: bool = False
    premium_access: bool = True

class ModuleAccessCreate(ModuleAccessBase):
    pass

class ModuleAccessUpdate(BaseModel):
    free_access: bool | None = None
    starter_access: bool | None = None
    premium_access: bool | None = None

class ModuleAccessResponse(ModuleAccessBase):
    id: int

    class Config:
        from_attributes = True
