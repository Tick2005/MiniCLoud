function getPostKey(suffix) {
  const pathname = window.location.pathname;
  const match = pathname.match(/(\d+)/);
  return match ? `blog${match[1]}` : 'blog';
}

function bindLikeButton() {
  const likeButton = document.getElementById("like-button");
  const likeCount = document.getElementById("like-count");
  if (!likeButton || !likeCount) return;

  const articleName = getPostKey("article");

  // Load initial like count from backend
  fetch(`/api/blog/likes/${articleName}`)
    .then((r) => r.json())
    .then((data) => {
      likeCount.textContent = String(data.likes || 0);
    })
    .catch(() => {
      // Fallback: use HTML value if API fails
    });

  likeButton.addEventListener("click", async () => {
    try {
      const res = await fetch(`/api/blog/like/${articleName}`, {
        method: "POST",
      });
      const data = await res.json();
      likeCount.textContent = String(data.likes || 0);
    } catch (err) {
      // Fallback: increment locally
      const next = Number(likeCount.textContent || "0") + 1;
      likeCount.textContent = String(next);
    }
  });
}

function bindComments() {
  const commentsSection = [...document.querySelectorAll(".widget")].find((el) => {
    const h3 = el.querySelector("h3");
    return h3 && h3.textContent.trim().toLowerCase() === "comments";
  });
  if (!commentsSection) return;

  const articleName = getPostKey("article");
  const listWrap = document.createElement("div");
  listWrap.id = "comment-list";
  commentsSection.querySelectorAll(".comment-item").forEach((node) => node.remove());

  function renderComments(comments) {
    listWrap.innerHTML = comments
      .map((item) => `<div class="comment-item"><strong>${item.author}:</strong> ${item.text}</div>`)
      .join("");
  }

  const form = document.createElement("form");
  form.id = "comment-form";
  form.innerHTML = `
    <input id="comment-name" type="text" placeholder="Your name" maxlength="40" required />
    <textarea id="comment-text" placeholder="Write a short comment..." maxlength="240" required></textarea>
    <button type="submit">Post comment</button>
  `;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const nameInput = form.querySelector("#comment-name");
    const textInput = form.querySelector("#comment-text");
    const name = (nameInput.value || "").trim();
    const text = (textInput.value || "").trim();
    if (!name || !text) return;

    try {
      const res = await fetch(`/api/blog/comment/${articleName}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ author: name, text: text }),
      });
      if (res.ok) {
        form.reset();
        // Reload comments from backend
        loadComments();
      }
    } catch (err) {
      console.error("Comment post failed:", err);
    }
  });

  function loadComments() {
    fetch(`/api/blog/comments/${articleName}`)
      .then((r) => r.json())
      .then((data) => {
        const comments = data.comments || [];
        renderComments(comments);
      })
      .catch((err) => {
        console.error("Failed to load comments:", err);
        renderComments([]);
      });
  }

  commentsSection.appendChild(listWrap);
  commentsSection.appendChild(form);
  
  // Load comments from backend on page load
  loadComments();
}

document.addEventListener("DOMContentLoaded", () => {
  bindLikeButton();
  bindComments();
});
