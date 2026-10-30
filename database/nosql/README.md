NoSQL Setup — TransitIQ
1. Get an LTA API Key
    1. Go to [LTA DataMall](https://datamall.lta.gov.sg/).
    2. Register for API access and obtain your Account Key.
    3. Keep the key private.

2. Install MongoDB
    1. Download [MongoDB Community Server](https://www.mongodb.com/try/download/community).
    2. Choose Windows → MSI.
    3. Run the installer and select Complete.
    4. Keep Install MongoD as a Service checked.
    5. Install MongoDB Compass when offered.
Open Compass and connect using:
mongodb://localhost:27017

**Do not create the database or collections manually. The scripts will create them.**

3. Install Python Packages
    Open a terminal in the project’s root folder and run:

    ```powershell
    python -m pip install pymongo requests python-dotenv
    ```

4. Add Your Settings
    Add these to the existing `backend/.env`, below the SQL settings:

    MONGO_URI=mongodb://localhost:27017/
    MONGO_DB=TransitIQ
    LTA_ACCOUNT_KEY=your_actual_key  **Replace your_actual_key with your LTA Account Key.**

5. Import the Data
    From the project root, run:

        ```powershell
        python database/scripts/density_import.py
        python database/scripts/alerts_import.py
        ```

    The scripts automatically create:
    TransitIQ
    ├── StationCrowdDensity
    └── TrainServiceAlert

6. Check Your Data
Refresh MongoDB Compass, open TransitIQ, and select each collection to view its documents.