from pydantic import BaseModel, Field
from typing import Optional

class CharacterDesignSheet(BaseModel):
    name: str = Field(..., description="Character name - must match story text")
    gender: str = Field(..., description="Gender: male / female / non-binary")
    age_range: str = Field(..., description="Age range: child / teen / young adult / adult / elder")
    hair_style: str = Field(..., description="Hair style (e.g. short spiky black hair)")
    hair_color: str = Field(..., description="Hair color")
    eye_color: str = Field(..., description="Eye color")
    body_type: str = Field(..., description="Body type")
    primary_outfit: str = Field(..., description="Primary outfit")
    distinguishing_features: str = Field(..., description="Distinguishing features")
    personality_note: str = Field(..., description="Personality note")

    class Config:
        populate_by_name = True

    def to_prompt_tokens(self) -> str:
        """
        Converts the design sheet to optimized SD prompt tokens.
        Order: gender -> age -> hair_style + hair_color -> eye_color -> primary_outfit -> distinguishing_features.
        Return comma-separated tokens.
        """
        tokens = []
        
        # Gender
        if self.gender:
            tokens.append(self.gender)
            
        # Age
        if self.age_range:
            tokens.append(f"{self.age_range} age" if self.age_range in ["child", "teen", "elder"] else self.age_range)
            
        # Hair style + hair color
        hair_parts = []
        if self.hair_style:
            hair_parts.append(self.hair_style)
        if self.hair_color:
            hair_parts.append(self.hair_color)
        if hair_parts:
            tokens.append(" ".join(hair_parts) if self.hair_style and self.hair_color else (self.hair_style or self.hair_color))
            
        # Eye color
        if self.eye_color:
            tokens.append(f"{self.eye_color} eyes")
            
        # Body type
        if self.body_type:
            tokens.append(self.body_type)

        # Primary outfit
        if self.primary_outfit:
            tokens.append(self.primary_outfit)
            
        # Distinguishing features
        if self.distinguishing_features:
            tokens.append(self.distinguishing_features)
            
        return ", ".join([t.strip() for t in tokens if t.strip()])

    def to_negative_tokens(self) -> str:
        """
        Returns prevent-drift tokens (e.g. "wrong hair color, feminine features, old age").
        """
        tokens = []
        
        # Add basic anti-drift tokens based on fields
        if self.gender == "male":
            tokens.append("feminine features, female, woman, girl")
        elif self.gender == "female":
            tokens.append("masculine features, male, man, boy")
            
        if self.age_range == "child" or self.age_range == "teen":
            tokens.append("old age, elder, wrinkles, mature face")
        elif self.age_range == "elder":
            tokens.append("childish face, young face, smooth skin")
            
        if self.hair_color:
            tokens.append("wrong hair color, different hair color")
            
        if self.hair_style:
            tokens.append("different hair style, wrong hair style")
            
        if self.eye_color:
            tokens.append("different eye color, wrong eye color")
            
        if self.primary_outfit:
            tokens.append("wrong outfit, different outfit, inconsistent clothing")
            
        if not tokens:
            tokens.append("character drift, inconsistent appearance")
            
        return ", ".join(tokens)
