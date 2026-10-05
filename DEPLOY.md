# Cloud demo copy: Supabase + Render + Vercel

No Docker needed. You sign in to each service; the repository already holds the settings.

What the cloud copy does not have: the MQTT live sensor feed, MinIO file storage, and PyTorch
(RUL comes from the XGBoost model; the anomaly score reads 0 when "Run prediction" is pressed).

## 1. GitHub

Create an empty **private** repository (no README), then push this folder to it:

    git remote add origin https://github.com/<you>/vayu-ready.git
    git push -u origin main

## 2. Supabase (database)

1. New project, region **Mumbai (ap-south-1)**. Choose a database password and keep it.
2. Project > **Connect** > **Session pooler**. Copy the connection string and put your password in it.
   It looks like `postgresql://postgres.<ref>:<password>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres`.

Use the session pooler string, not "Direct connection" (that one is IPv6 only and Render cannot reach it).

## 3. Render (API)

1. **New > Blueprint**, pick the GitHub repository. Render reads `render.yaml`.
2. When asked:
   - `DATABASE_URL` = the Supabase string from step 2
   - `CORS_ORIGINS` = `https://placeholder.vercel.app` for now (fixed in step 5)
3. Deploy. On first start the API creates the tables and loads the synthetic demo data (about a minute).
4. Open `https://<your-service>.onrender.com/health`; it should say `"status": "ok"`. Copy the service URL.

## 4. Vercel (web)

1. **Add New > Project**, import the same repository.
2. **Root Directory** = `frontend`. Framework is detected as Next.js.
3. Environment variable: `NEXT_PUBLIC_API_URL` = the Render URL from step 3 (no trailing slash).
4. Deploy and copy the Vercel URL.

## 5. Connect the two

In Render > the service > **Environment**, set `CORS_ORIGINS` to the Vercel URL (no trailing slash) and save. Render restarts the API.

Open the Vercel URL, tap **Squadron Commander** under Demo accounts, press **Verify code**. The score should be 71.

## Good to know

- Render's free plan sleeps after 15 minutes without traffic; the first request then takes up to a minute. Open the site a few minutes before judges do.
- **Reset demo** (Admin) reloads the data so the score is 71 again.
- The login page shows the demo password and code. That is intended for judges; anyone with the link can log in to the demo data.
- The cloud copy connects to the database as the Supabase owner, so PostgreSQL row-level security is not what enforces squadron privacy there; the API's own role and squadron checks do.
