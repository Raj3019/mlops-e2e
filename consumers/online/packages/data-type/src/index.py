from dataclasses import dataclass
from typing import Optional

@dataclass
class DataType:
    sex: str  # 'I', 'F', or 'M'
    length: float
    diameter: float
    height: float
    whole_weight: float
    shucked_weight: float
    viscera_weight: float
    shell_weight: float
    
    id: str
    predict: Optional[float] = None  # Prediction can be optional
    actual: Optional[float] = None  # Actual can be optional

@dataclass
class AddLabelRequest:
    actual: float