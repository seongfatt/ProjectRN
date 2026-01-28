# data_manager.py - FULL DATASETS LIBRARY APPROACH
import pandas as pd
import os
from datetime import datetime
from config import PLOT_TYPES, TOTAL_PLOTS, TYPE_MAP, PHYSICAL_ORDER, HF_REPO_ID

CSV_FILE = "garden_roster.csv"

def load_data():
    """Load data using datasets library"""
    try:
        from datasets import load_dataset
        
        print("📡 Loading dataset...")
        
        # Try to load the dataset
        try:
            # If dataset exists, load it
            dataset = load_dataset(HF_REPO_ID)
        except:
            # If dataset doesn't exist, create from local CSV
            if os.path.exists(CSV_FILE):
                dataset = load_dataset("csv", data_files=CSV_FILE)
            else:
                # Create new data
                return create_new_data()
        
        # Convert to pandas
        if isinstance(dataset, dict):
            # Get first split
            split_name = list(dataset.keys())[0]
            df = dataset[split_name].to_pandas()
        else:
            df = dataset.to_pandas()
        
        print(f"✅ Loaded {len(df)} records")
        return df
        
    except Exception as e:
        print(f"❌ Error using datasets: {e}")
        return fallback_load()

def create_new_data():
    """Create initial DataFrame"""
    df = pd.DataFrame({
        "Plot": PHYSICAL_ORDER,
        "Name": [""] * TOTAL_PLOTS,
        "Contact": [""] * TOTAL_PLOTS,
        "Type": [TYPE_MAP[i] for i in PHYSICAL_ORDER],
        "Change": [""] * TOTAL_PLOTS,
        "Plot_confirm": [None] * TOTAL_PLOTS,
        "Occupy": [False] * TOTAL_PLOTS,
        "User_ID": [""] * TOTAL_PLOTS
    })
    return df

def fallback_load():
    """Fallback to local file loading"""
    try:
        if os.path.exists(CSV_FILE):
            df = pd.read_csv(CSV_FILE)
            print(f"✅ Loaded from local: {CSV_FILE}")
            return df
    except Exception as e:
        print(f"❌ Error loading local: {e}")
    
    # Create new
    print("📝 Creating new data...")
    df = create_new_data()
    return df

def save_data(df):
    """Save data locally and optionally to Hugging Face"""
    # Save locally
    df.to_csv(CSV_FILE, index=False)
    print(f"💾 Saved locally: {CSV_FILE}")
    
    # Try to push to Hugging Face
    try:
        from huggingface_hub import HfApi
        import tempfile
        
        api = HfApi()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            tmp_path = f.name
            df.to_csv(tmp_path, index=False)
        
        api.upload_file(
            path_or_fileobj=tmp_path,
            path_in_repo=CSV_FILE,
            repo_id=HF_REPO_ID,
            repo_type="dataset",
            commit_message=f"Updated {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        
        os.unlink(tmp_path)
        print("✅ Pushed to Hugging Face!")
        
    except Exception as e:
        print(f"⚠️ Note: Could not push to Hugging Face: {e}")
        print("   Data is saved locally and will work fine")
    
    return True