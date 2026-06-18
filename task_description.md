## System Design Interview Assignment

## **AI Processing Platform — System Architecture Design**

## Assignment Objective

Please design a scalable and operable **AI Processing Platform** that integrates Speech-to-Text (STT), text summarization (LLM), and result query services, while taking into account high-concurrency processing, cloud deployment, monitoring, fault tolerance, and observability. This assignment does not require you to implement a complete backend, but we hope to see your overall planning mindset for the system.

## Task Content

Please complete the following items, and you may choose a familiar IaaS such as GCP, AWS, Azure, or Alibaba Cloud for your explanation (you may use diagrams, written documentation, or short demo programs to support your design):

## Architecture Design

Design an overall architecture for an operational AI task processing platform. Below is a reference module list (just for reference):

- Frontend Website / API Gateway

- Task Processing Modules (STT, LLM), you may assume your own concurrency limits

- Message Queue

- Database or Cache

OSS

Log System / Metrics / Alerting

Monitoring and Observability

And assume the task flow is as follows:

User uploads audio → STT Service converts to text → LLM Service summarizes → Stores result → Queries result

## Please present:

- System architecture diagram

- Task sequence diagram or data flow diagram

- Logical boundaries and responsibilities of each service

## Technology Selection and Rationale

## Please describe what you would adopt:

- Programming language and framework (Node.js, Python, Go…)

- Cloud platform and services (AWS / GCP / Azure / self-hosted)

- Database, cache, and message queue (PostgreSQL, Redis, RabbitMQ, Kafka…)

- Model service deployment strategy (API mode, Container mode, local inference)

Please explain the reasoning and trade-offs behind your choices.

## Architecture Characteristics Explanation

Please briefly describe your system's design strategy in the following aspects:

| Aspect | Direction of Explanation |
|---|---|
| Scalability | How to handle surges in user count or task volume? |
| Fault Tolerance | When a service fails, how does the system automatically recover? |
| Data Consistency | How to ensure STT/LLM results are correctly written? |
| Latency & Performance | How to reduce the impact of LLM latency on user experience? |
| Security | How to protect uploaded files and API access security? |
| Observability | How to monitor and trace each task and overall system health? |



## Operations and Deployment

## Please provide:

- A simple deployment topology diagram (Dev / Staging / Prod architecture)

- CI/CD process diagram

- Brief description of how to perform version updates and rollback.

## Document Deliverables

- Please submit a document containing the following (Markdown or PDF acceptable):

   - Architecture diagram and sequence diagram

   - Technology selection explanation

   - Architecture decision summary

   - Deployment and operations strategy summary

   - If you have extra capacity, you may attach a simple prototype or mock service

## Bonus Points

| Item | Bonus Conditions |
|---|---|
| Cloud Mindset | Architecture includes multi-region deployment, CDN, load balancing, or Serverless components |
| Automation | Proposes CI/CD, testing, and monitoring integration solutions |
| Flexible Design | Architecture supports plug-in style tasks (future AI tasks can be added) |
| Documentation | Architecture explanation is clear with smooth logic between text and diagrams |
| Implementation Supplement | Including a simple demo (Node.js + queue + mock STT/LLM) is even better |



## Submission Content

## Please provide:

1. A primary design document (`ARCHITECTURE.md` or PDF)

2. System architecture diagram and sequence diagram

3. (Optional) A minimal executable prototype (docker-compose startable mock services) 4. (Optional) Presentation version (for subsequent interview demonstration)

## Scoring Focus

| Aspect | Evaluation Focus |
|---|---|
| System Architecture Capability | Clear architecture, well-defined component responsibilities |
| Technical Judgment | Technology selection and trade-offs are well-reasoned |
| Scalability & Fault Tolerance | Considerations for high concurrency and high availability |
| Documentation Quality | Clear and easy to understand |
| Expression Ability | Able to clearly explain design logic through text and diagrams |



## Additional Notes

We hope to see how you design a system that "can withstand pressure and evolve quickly." A completely correct answer is not required—rather, we want to see your trade-off thinking and technical decision-making logic.
