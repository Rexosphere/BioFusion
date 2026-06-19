import os
import json
import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms, models
from torchvision.models import DenseNet121_Weights
from torch.utils.data import DataLoader
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

def main():
    # Paths
    data_dir = 'data/chest_xray'
    train_dir = os.path.join(data_dir, 'train')
    val_dir = os.path.join(data_dir, 'val')
    test_dir = os.path.join(data_dir, 'test')
    
    models_dir = 'models'
    config_dir = 'config'
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(config_dir, exist_ok=True)
    
    model_save_path = os.path.join(models_dir, 'Pneumonia_DenseNet121_Final.pth')
    class_mapping_path = os.path.join(models_dir, 'class_to_idx.json')
    metrics_save_path = os.path.join(config_dir, 'model_metrics.json')

    # Hyperparameters
    batch_size = 32
    num_epochs = 10
    learning_rate = 1e-4

    # Device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    # Transforms
    data_transforms = {
        'train': transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(10),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
        'val': transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
        'test': transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
    }

    # Datasets and DataLoaders
    image_datasets = {
        'train': datasets.ImageFolder(train_dir, data_transforms['train']),
        'val': datasets.ImageFolder(val_dir, data_transforms['val']),
        'test': datasets.ImageFolder(test_dir, data_transforms['test'])
    }
    
    dataloaders = {
        'train': DataLoader(image_datasets['train'], batch_size=batch_size, shuffle=True, num_workers=4),
        'val': DataLoader(image_datasets['val'], batch_size=batch_size, shuffle=False, num_workers=4),
        'test': DataLoader(image_datasets['test'], batch_size=batch_size, shuffle=False, num_workers=4)
    }

    # Save class mapping
    class_to_idx = image_datasets['train'].class_to_idx
    with open(class_mapping_path, 'w') as f:
        json.dump(class_to_idx, f, indent=4)
    print(f"Class mapping saved to {class_mapping_path}")

    # Model setup
    print("Loading DenseNet121 model...")
    model = models.densenet121(weights=DenseNet121_Weights.IMAGENET1K_V1)
    num_ftrs = model.classifier.in_features
    # Replace classifier head for 2 classes
    model.classifier = nn.Linear(num_ftrs, len(class_to_idx))
    model = model.to(device)

    # Loss and Optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=learning_rate)

    # Training Loop
    best_val_acc = 0.0

    print("Starting training...")
    for epoch in range(num_epochs):
        print(f"Epoch {epoch+1}/{num_epochs}")
        print('-' * 10)

        for phase in ['train', 'val']:
            if phase == 'train':
                model.train()
            else:
                model.eval()

            running_loss = 0.0
            running_corrects = 0

            for inputs, labels in dataloaders[phase]:
                inputs = inputs.to(device)
                labels = labels.to(device)

                optimizer.zero_grad()

                with torch.set_grad_enabled(phase == 'train'):
                    outputs = model(inputs)
                    _, preds = torch.max(outputs, 1)
                    loss = criterion(outputs, labels)

                    if phase == 'train':
                        loss.backward()
                        optimizer.step()

                running_loss += loss.item() * inputs.size(0)
                running_corrects += torch.sum(preds == labels.data)

            epoch_loss = running_loss / len(image_datasets[phase])
            epoch_acc = running_corrects.double() / len(image_datasets[phase])

            print(f"{phase.capitalize()} Loss: {epoch_loss:.4f} Acc: {epoch_acc:.4f}")

            # Save best model
            if phase == 'val' and epoch_acc > best_val_acc:
                best_val_acc = epoch_acc
                torch.save(model.state_dict(), model_save_path)
                print(f"Saved new best model with validation accuracy: {best_val_acc:.4f}")

        print()

    print("Training complete.")
    print(f"Best Validation Accuracy: {best_val_acc:.4f}")

    # Evaluation on Test Set
    print("Evaluating on test set...")
    model.load_state_dict(torch.load(model_save_path, map_location=device))
    model.eval()

    all_preds = []
    all_labels = []

    with torch.no_grad():
        for inputs, labels in dataloaders['test']:
            inputs = inputs.to(device)
            labels = labels.to(device)
            outputs = model(inputs)
            _, preds = torch.max(outputs, 1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

    # Calculate metrics
    acc = accuracy_score(all_labels, all_preds)
    prec = precision_score(all_labels, all_preds, average='weighted', zero_division=0)
    rec = recall_score(all_labels, all_preds, average='weighted', zero_division=0)
    f1 = f1_score(all_labels, all_preds, average='weighted', zero_division=0)
    cm = confusion_matrix(all_labels, all_preds)

    print("Test Metrics:")
    print(f"Accuracy: {acc:.4f}")
    print(f"Precision: {prec:.4f}")
    print(f"Recall: {rec:.4f}")
    print(f"F1 Score: {f1:.4f}")
    print("Confusion Matrix:")
    print(cm)

    # Save metrics to JSON (real metrics, not faked)
    metrics_dict = {
        "accuracy": float(acc),
        "precision": float(prec),
        "recall": float(rec),
        "f1_score": float(f1),
        "confusion_matrix": cm.tolist()
    }
    
    with open(metrics_save_path, 'w') as f:
        json.dump(metrics_dict, f, indent=4)
    print(f"Metrics saved to {metrics_save_path}")

if __name__ == '__main__':
    main()
