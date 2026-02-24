Project upload flow
===================

This document describes Ambuda's project upload flow.


Overview
--------

Ambuda's proofreading pipeline converts scanned books into structured and machine-readable text. The
first step in our pieline is to accept a scanned PDF and turn it into a project ready for
proofreading.

At a high-level, the flow is as follows:

1. The user navigates to the "Create project" page and submits one or more PDFs. On submit, the
   user is redirected to a status page where they can monitor their upload.
2. On submit, the server temporarily stores the user's PDF on the server and starts an asynchronous
   Celery task to process the PDF.
3. The Celery task splits each PDF into separate pages and stores them on S3.
4. For each PDF, the task creates a project entry in the database with basic metadata and a list
   of all pages.
5. The task stores the uploaded PDFs on S3, cleans up any temporary files, and completes.
6. The user is notified that the project is ready.


Key files
---------

Templates:
- ambuda/templates/proofing/create-project.html -- upload page
- ambuda/templates/proofing/create-project-post.html -- upload status page

Backend:
- ambuda/views/proofing/main.py -- Flask routes
- ambuda/tasks/projects.py -- Celery tasks for creating projects
- ambuda/models/proofing.py -- database model for projects, pages, etc.


Authorization
-------------

Due to the high potential for abuse, this flow is visible only to users with the P2 user role.
Unauthorized users who try to access this flow should be redirected to the proofing main page at
/proofing.


1. Getting the PDF
------------------

An authorized user may submit PDFs in one of three ways:

- direct upload from the user's computer
- upload via public URL, such as from archive.org
- upload via multiple public URLs

Upon submission, the site redirects the user to a status page, which we describe further in step
(6) below.

Notes:

- The user is required to specify a title for each of the PDFs uploaded, since a title both
  describes the project and makes the project searchable.

- Duplicate titles are acceptable. But if a title is a duplicate, the UI warns the user that this
  has occurred. The rationale is that the user may accidentally be duplicating an existing project.

- Upon submit, the backend converts the title into a unique *slug* for the project. Titles do not
  have to be unique, but slugs must be. If the system detects a collision, it will automatically
  generate a replacement slug and use that instead.

- If a PDF is uploaded by URL, we perform the download in the Celery task, NOT in the route.
  This is so that we don't stress the web process, which should be lightweight and low latency.


2. Starting the task
--------------------

Each of the three cases above has its own corresponding Celery task. Each task begins by ensuring
that the PDFs it needs are accessible.

- For direct upload, the PDF should already exist as a temporary file.
- For upload via URL, the task creates a new temporary path and downloads it there.
- For multi-upload via URL, the task processes PDFs serially: it downloads one PDF, completes all
  work required for that PDF, cleans up state, and only *then* does it download the next PDF.

The most complex task here is multi-upload, which deserves more explanation.

If we download multiple PDFs in parallel, we run the following risks:

- being blocked for abusive activity by archive.org or other file sites
- exhausting available disk space on the server, especially if the user is uploading many large
  PDFs.
- blowing up memory due to the high resource requirements of processing a single PDF. For example,
  I once tried a small test with two large PDFs in parallel and brought the server to a crawl.

For these reasons, we also avoid farming out a multi-upload to separate Celery tasks. A single
Celery task can handle this workload serially and carefully manage resource usage along the way.

Since multi-upload may require more processing time, the task has an extended time limit of two
hours.


3. Splitting the PDF
--------------------

We use the `fitz` library to read the data from a PDF's page into a usable image.

- We have no preference on the specific file format used. For now, we have defaulted to jpeg.
- API restrictions require us to first write the page to disk. Once saved, the page is immediately
  written to S3 and cleaned up from local disk.


4. Creating a project
---------------------

Once all pages are processed, the task creates a Project entry in the database.

Since the project needs additional review for copyright, quality, and other potential issues, it
is kept in the *pending* state.


5. Completing the task
----------------------

Upon completion, the task cleans up its temporary files to free up disk space.


6. Notifying the user
---------------------

The user receives information from their task through a status page, which describes the task and
its overall progress. This status pages makes a simple poll to the server every 5 seconds for task
information.

- If the user's task is still in the queue, the page lets the user know where they are in the
  queue. The idea is to give the user timely feedback on their request.

- Each status link contains the task ID. We include the task ID explicitly in the URL so that the
  user can refer back to this task later and so that the user can recover if they accidentally
  close the page.

- Upon success, the status page includes a link to all projects that the task created.

- For multi-upload, the status page gives a breakdown by PDF so that the user has an exact
  understanding of the task's overall progress.

