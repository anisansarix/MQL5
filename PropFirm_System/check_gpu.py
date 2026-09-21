import torch
print(f"PyTorch Version: {torch.__version__}")
print(f"GPU Enabled: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU Device: {torch.cuda.get_device_name(0)}")
    print(f"CUDA Version: {torch.version.cuda}")
