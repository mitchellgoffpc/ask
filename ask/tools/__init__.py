from dataclasses import dataclass

@dataclass
class Parameter:
    name: str
    type: str
    description: str = ''
    required: bool = True
    enum: list[str] | None = None

class Tool:
    name: str
    description: str
    parameters: list[Parameter]

    @classmethod
    def execute(cls, *args, **kwargs):
        raise NotImplementedError("Subclasses should implement this method.")


class StockPriceTool(Tool):
    name = "get_stock_price"
    description = "Retrieves the current stock price for a given company"
    parameters = [
        Parameter(name="company", type="string", description="The company name to fetch stock data for")
    ]
