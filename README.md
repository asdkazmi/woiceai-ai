# WoiceAI AI services

WoiceAI is a platform for building AI assistants and conversational workflows powered by your own knowledge.

Create knowledge bases from documents, text, websites, audio, images, and video; configure assistants with custom instructions, retrieval settings, and citations; and connect them through visual workflows.

This repository contains the Python services for chat, retrieval, knowledge-base processing, and website crawling.

## Documentation

Visit the complete **[WoiceAI Documentation](https://woiceai.github.io/)** for:

- Architecture and required services
- Installation, configuration, and deployment
- AWS Lambda, ECR, S3, and SNS integration
- RunPod chat, embedding, transcription, and vision services
- MongoDB Atlas vector indexing and knowledge-base synchronization
- Chat settings, models, citations, and workflow execution
- Environment templates, API examples, and troubleshooting

You can also [browse the documentation directly on GitHub](https://github.com/woiceai/woiceai.github.io).

## Source repositories

| Repository | Purpose |
| --- | --- |
| [woiceai-web](https://github.com/asdkazmi/woiceai-web) | React frontend and Express backend: authentication, knowledge-base management, assistant configuration, chat, connectors, and the visual workflow builder. |
| [woiceai-ai](https://github.com/asdkazmi/woiceai-ai) | Core AI services: document ingestion, website crawling, indexing, retrieval, and the RunPod chat and embedding backend. Services are maintained on separate branches. |
| [woiceai-transcriber](https://github.com/asdkazmi/woiceai-transcriber) | RunPod audio transcription service, including optional speaker diarization and transcript indexing. |
| [woiceai-vision](https://github.com/asdkazmi/woiceai-vision) | RunPod image and video processing: visual explanations, sampled scene descriptions, video speech transcription, and knowledge-base indexing. |
| [woiceai.github.io](https://github.com/woiceai/woiceai.github.io) | Central documentation, deployment guides, configuration templates, and operational references. |

### AI service branches

In **woiceai-ai**, use the branch corresponding to the service:

| Branch | Purpose |
| --- | --- |
| [`chat-all-models`](https://github.com/asdkazmi/woiceai-ai/tree/chat-all-models) | Primary RunPod chat, embedding, and retrieval backend. Its build context is `chat-with-all-models/`. |
| [`dev-woiceai-kb`](https://github.com/asdkazmi/woiceai-ai/tree/dev-woiceai-kb) | AWS Lambda knowledge-base worker for document processing, media dispatch, indexing, and deletion. |
| [`dev-scrapper`](https://github.com/asdkazmi/woiceai-ai/tree/dev-scrapper) | AWS Lambda website scraper used for page extraction and depth-based crawling. |

The `main` branch contains the project overview and license. Each service branch contains its own code snapshot. Follow the [deployment documentation](https://woiceai.github.io/docs/setup/README.html) when selecting branches and configuring the complete system.

## How it works

The React and Express application manages users, knowledge bases, assistants, and workflows and can be deployed on **AWS EC2** or a comparable hosting platform. Original files are stored in an **Amazon S3** bucket. **AWS Lambda** workers coordinate ingestion and website crawling, while **RunPod** workers handle embeddings, chat, transcription, and visual processing.

Extracted content and vectors are stored in **MongoDB Atlas** for retrieval. **MySQL** stores application metadata and workflow state. **Amazon SNS** carries indexing requests and status updates between processing workers and the web application.

For the complete architecture and setup instructions, start at **[woiceai.github.io](https://woiceai.github.io/)**.
