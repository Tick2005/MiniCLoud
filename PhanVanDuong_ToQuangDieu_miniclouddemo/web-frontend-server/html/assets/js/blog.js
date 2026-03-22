function bindLikeButton() {
  const likeButton = document.getElementById("like-button");
  const likeCount = document.getElementById("like-count");
  if (!likeButton || !likeCount) return;

  likeButton.addEventListener("click", () => {
    const current = Number(likeCount.textContent || "0");
    likeCount.textContent = String(current + 1);
  });
}

document.addEventListener("DOMContentLoaded", bindLikeButton);
