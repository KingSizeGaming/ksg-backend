async function previewAsset(path, activityId) {
    try {
      const response = await fetch(`/preview_asset?path=${encodeURIComponent(path)}`);
      const data = await response.json();
      const imgPreview = document.getElementById("imagePreview");
  
      if (data.url) {
        imgPreview.src = data.url;
        const comments = await fetchComments(activityId);
        displayComments(comments);
        document.getElementById("new-comment").dataset.activityId = activityId; // Set the activityId as a data attribute on the textarea
        console.log(`Set activityId: ${activityId} on comment textarea`); // Debug log
        showModal("previewModal");
      } else {
        imgPreview.src = "";
        document.querySelector("#previewModal .modal-body").innerHTML = "This file type cannot be previewed.";
        showModal("previewModal");
      }
    } catch (error) {
      console.error("Error fetching preview:", error);
      alert("Error fetching preview.");
    }
  }
  
  async function fetchComments(activityId) {
    try {
      const response = await fetch(`/get_comments/${activityId}`);
      return await response.json();
    } catch (error) {
      console.error("Error fetching comments:", error);
      return [];
    }
  }
  
  function displayComments(comments) {
    const commentsDiv = document.getElementById("comments");
    if (comments.length > 0) {
      let commentsContent = "<h3>Comments:</h3>";
      comments.forEach(comment => {
        commentsContent += `<p>${comment.author}: ${comment.comment} - ${new Date(comment.created_at).toLocaleString()}</p>`;
      });
      commentsDiv.innerHTML = commentsContent;
    } else {
      commentsDiv.innerHTML = "<p>No comments for this file.</p>";
    }
  }
  
  async function addComment() {
    const commentText = document.getElementById("new-comment").value;
    const activityId = document.getElementById("new-comment").dataset.activityId;
  
    console.log(`Adding comment for activityId: ${activityId}`); // Debug log
  
    if (!activityId) {
      console.error("No activity ID found for adding comment.");
      return;
    }
  
    try {
      const response = await fetch("/add_comment", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ activity_log_id: activityId, comment: commentText }),
      });
  
      if (response.ok) {
        const comments = await fetchComments(activityId);
        console.log(comments);  // Log fetched comments to ensure they are retrieved correctly
        displayComments(comments);
      } else {
        console.error("Error adding comment:", await response.json());
      }
    } catch (error) {
      console.error("Error adding comment:", error);
    }
  }
  
  async function approveAsset(id) {
    try {
      const response = await fetch(`/approve_asset/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await response.json();
      console.log(data);
      location.reload();
    } catch (error) {
      console.error('Error:', error);
    }
  }
  
  function showModal(id) {
    const modal = document.getElementById(id);
    modal.style.display = "flex";
  }
  
  function closeModal(id) {
    const modal = document.getElementById(id);
    modal.style.display = "none";
  }
  
  