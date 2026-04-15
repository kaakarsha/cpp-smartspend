SpendSmart – Expense Tracking System - CPP Project

SpendSmart is a cloud-based web application that helps users track, manage, and analyze their daily expenses efficiently. It provides real-time insights, CSV export functionality, and automated email notifications using AWS services.

🚀 Features
🔐 User Authentication (Login system)
📊 Dashboard with expense analytics & graphs
➕ CRUD operations for managing expenses
📁 Export expense reports as CSV
📧 Email notifications for transactions & reports
📈 Expense-to-income percentage calculation
☁️ Fully deployed on AWS Cloud
🛠️ Tech Stack

Frontend & Backend

Python (Flask)
HTML, CSS, JavaScript

Cloud & Services (AWS)

Elastic Beanstalk – App deployment
RDS (PostgreSQL) – Database
S3 – File storage (CSV reports)
SNS – Email notifications
Lambda – Serverless computations
API Gateway – API management
Cloud9 – Development environment
📦 Custom Library

A custom PyPI library is used to calculate average expenses:

pip install average-expense-lib

URL: http://spendsmart.us-east-1.elasticbeanstalk.com/login

⚙️ How It Works
User logs into the system
Adds/updates/deletes expenses
Dashboard displays insights and charts
Expenses can be exported as CSV
Email notifications are triggered via AWS SNS
Analytics (average & percentage) computed using Lambda
📁 Project Structure (Example)
├── application.py
├── templates/
├── static/
├── requirements.txt
└── README.md
🔄 CI/CD
GitHub Actions is used for automation
Automatically builds and deploys on code push
🎯 Objectives
Efficient expense tracking system
Secure and scalable cloud-based architecture
Real-time analytics and reporting
Integration of multiple AWS services
📌 Future Improvements
Multi-user support
Mobile app integration
Budget alerts & recommendations
Advanced analytics
