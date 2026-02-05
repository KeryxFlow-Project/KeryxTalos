

import asyncio
from textual.app import App, ComposeResult
from textual.widgets import DataTable
from keryxflow.core.database import init_db
from keryxflow.exchange.paper import PaperTradingEngine, set_paper_engine
from keryxflow.hermes.widgets.balance import BalanceWidget

class VerificationApp(App):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.widget = BalanceWidget()
        self.widget.set_paper_engine(engine)

    def compose(self) -> ComposeResult:
        yield self.widget

    async def on_mount(self):
        with open("verification_results.txt", "w") as f:
            f.write("App mounted. Running verification steps...\n")
            
            # Manually trigger refresh logic to test it
            f.write("Calling refresh_data()...\n")
            try:
                await self.widget.refresh_data()
                f.write("refresh_data() completed.\n")
            except Exception as e:
                f.write(f"CRASH in refresh_data: {e}\n")
                import traceback
                f.write(traceback.format_exc())
                f.write("\n")

            # Inspect Results
            f.write("\n--- RESULTS ---\n")
            f.write(f"Widget internal balances: {self.widget._balances}\n")
            
            table = self.widget.query_one("#balance-table", DataTable)
            f.write(f"Table Row Count: {len(table.rows)}\n")
            
            if len(table.rows) > 0:
                f.write("Table Rows:\n")
                for key, row in table.rows.items():
                    # Get values for the row
                    values = table.get_row(key)
                    f.write(f"  {values}\n")
            else:
                f.write("FAILURE: Table is empty!\n")
                
        self.exit()

async def verify_widget():
    print("--- STARTING VERIFICATION ---")
    
    # 1. Initialize DB
    print("Initializing DB...")
    await init_db()
    
    # 2. Setup Engine
    print("Setting up Paper Engine...")
    engine = PaperTradingEngine()
    await engine.initialize()
    set_paper_engine(engine)
    
    # Check engine balance directly
    balance = await engine.get_balance()
    print(f"Engine Balance: {balance}")
    
    # 3. Run App
    print("Initializing App...")
    app = VerificationApp(engine)
    await app.run_async()

if __name__ == "__main__":
    asyncio.run(verify_widget())

