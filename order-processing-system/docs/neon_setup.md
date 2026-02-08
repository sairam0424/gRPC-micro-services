# Neon PostgreSQL Setup and Connection Guide

This guide provides instructions on how to manage your database using the Neon Web Console and pgAdmin.

## 1. Neon Web Console

The Neon Web Console is the easiest way to view your tables and run queries.

1.  **Login**: Go to [console.neon.tech](https://console.neon.tech).
2.  **Select Project**: Choose your project (e.g., `your-neon-project`).
3.  **Data Editor**: 
    - Click on **"SQL Editor"** in the left sidebar to run custom queries.
    - Click on **"Tables"** to browse your schema and view data in the `inventory` table.
4.  **Monitoring**: View real-time metrics and query performance in the **"Dashboard"** tab.

## 2. Connecting with pgAdmin 4

If you prefer a desktop tool like pgAdmin, follow these steps:

1.  **Open pgAdmin**: Start pgAdmin 4 on your machine.
2.  **Add New Server**:
    - Right-click "Servers" > "Register" > "Server...".
    - **General Tab**: Name it "Neon PostgreSQL".
    - **Connection Tab**:
        - **Host**: `<your-project-id>-pooler.<region>.aws.neon.tech`
        - **Port**: `5432`
        - **Maintenance database**: `neondb`
        - **Username**: `neondb_owner`
        - **Password**: `<your-password>`
    - **Parameters Tab**:
        - Add a new row: Name: `sslmode`, Value: `require`.
3.  **Save**: Click Save. You should now be able to browse the `neondb` database.

## 3. Database URL Structure

The URL used in the application is:
`postgresql://<user>:<password>@<hostname>/neondb?sslmode=require`

> [!NOTE]
> The `sslmode=require` query parameter is critical for cloud-hosted databases in Neon.

## 4. Troubleshooting

- **Connection Refused**: Ensure your `sslmode` is set to `require`.
- **Authentication Failed**: Verify the password. Note that Neon passwords are case-sensitive.
- **Port 5432 Blocked**: Ensure your local firewall or network allows outbound traffic on port 5432.
