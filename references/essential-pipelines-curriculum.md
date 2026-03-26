# Essential Pipelines curriculum

This curriculum defines the core concepts and learnings necessary for a user to get started with Buildkite Pipelines and embody the “Buildkite Way 🙏🏻.”

# Curriculum intent

We intend to use these concepts as the foundation of our onboarding flow. They focus on what a first-time user should understand to set themselves up for success with Pipelines and put them on the path to becoming a Buildkite advocate. 

It doesn't consider how we'll teach these concepts to new users, their order, or what will make the experience magical. Those will come next and build on top of this work.

# Core concepts

The content of each concept is broken down into the following categories:
- Essential: A user must understand this to get started with Buildkite.
- Important: Everyone should know these to get started, but it’s okay if they have to come back to learn them when they’re creating their own pipelines.
- Advanced: These are advanced topics in Buildkite and aren't required for everyone. They 
might be important to a user depending on their use case and role.

The concepts are not listed in any particular order.

# Zero-trust security model
It’s essential that I understand Buildkite never sees the code.

It’s important that I understand:
- Agents have permission to access the code in my SCM through SSH authentication.
- I need to connect Pipelines to my SCM to support outbound integrations from Buildkite. For example, linking back to pull requests and branches.
- There are different paths to connect my SCM depending on which SCM I use.
- I control my secret management.
- Agents are authenticated to my organisation with my agent token.
 
I should have awareness of and understand how to learn more about the following concepts:
- I can define the scope of permissions I grant to the agent to keep the code secure.  

# Self-hosting an agent
- It’s essential that I understand that to run builds on Buildkite I need to
- install an agent on my own infrastructure.

It’s important that I understand:
- I can install the agent on my local machine or cloud compute.
- Agents are assigned work from Pipelines to run on my infrastructure.
- The agent communicates the outcome of builds to Buildkite, which I can view in Pipelines.

I should have awareness of and understand how to learn more about the following concepts:
- I can categorise my agents using clusters and job queues so that I can manage the work an agent does for a team.
- I can tune the performance of my build queue by scaling to multiple agents.
- I can host multiple agents for different use cases. For example, mobile testing, Mac.
- I can track the status of an agent in Pipelines.

# Creating a pipeline
It’s essential that I understand pipelines can be used to achieve many goals, including running tests, building artifacts, deploying executables, and automating workflows.

It’s important that I understand:
A pipeline is composed of one or more different types of steps.
A command step runs one or more shell commands on one or more agents. They spawn jobs.
I can define environment variables to manage secrets and configuration.
I can define and upload a pipeline from code.
I can define a pipeline in the visual editor.

I should have awareness of and understand how to learn more about the following concepts:
- I can run builds or steps only when specific conditions are met.
- I can define dependencies between steps to ensure proper ordering.
- You can store the outputs of a job as artifacts.
- Artifacts can be used to decompose a complex pipeline into simple steps.
- You can choose where artifacts are stored, including on the file system of the machine the agent is run on, an artifact store like Artifactory, or your own storage like an S3 bucket.
- A block step is used to pause the execution of a build.
- A wait step pauses a build from progressing until all previous jobs have completed.
- A trigger step creates a build on another pipeline.
- An input step is used to collect information from a user.
- A group step can contain various sub-steps, and display them in a single logical group on the Build page.
- I can use metadata to store and retrieve data between different steps

# Running a build
It’s essential that I understand a build is an execution of a pipeline.

It’s important that I understand:
- A job is the execution of a command step.
- When a build is running, I can see real-time updates by watching the logs output by each job.
- Buildkite retains the logs for builds
- A build will always finish in one of the following states:
  - Failed
  - Cancelled
  - Pending
  - Success
- There are multiple ways to trigger a build:
  - New build button
  - Scheduled builds
  - Webhooks from SCM
  - Trigger step
  - API

I should have awareness of and understand how to learn more about the following concepts:
- I can cancel a running build.
- I can see previous runs of a build. These remain depending on the plan I have.
- I can receive notifications of the build result in multiple ways, including email and integrations with tools like Slack.
- If a build was picked up by an agent and fails, I can retry that build.
- If a job fails and I believe the issue is localised to that job, I can just retry that job.
- If a build was never picked up by an agent and fails, I can create a new build.
- I can optimise the performance of my builds by running steps in parallel.

# Extensibility
It’s essential that I understand Buildkite supports completely custom workflows.

It’s important that I understand: 
- I can dynamically generate pipelines during a build.
- I can write or use third-party plugins to customise the behaviour of my steps.
- I can use hooks to extend the behaviour of a regular pipeline for my specific use case.

I should have awareness of and understand how to learn more about the following concepts:
- I can use infrastructure-as-code tools like Terraform to manage pipelines and agents.
- I can fully customise Pipelines through the APIs.
- I can personalise builds more through emojis, annotations, and images.
- Integrating my SCM lets me use extra functionality like status checks, which prevent further actions without passing builds.
