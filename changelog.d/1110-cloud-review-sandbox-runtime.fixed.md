- Make the governed #1110 Codespaces SSH transport start through the same
  serialized control from both the image entrypoint and the post-create
  lifecycle, and require an exact image build-and-boot smoke in pull requests.
