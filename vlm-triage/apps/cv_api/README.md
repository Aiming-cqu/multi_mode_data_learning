# CV API

Computer Vision-based image similarity computation API using traditional CV algorithms like SIFT.

## Features

- Compute image similarities using SIFT and other CV algorithms
- Compare images against base (index 0) and feature (index -1) references
- Multiple output formats: Arrow, Parquet, Safetensors

## Running

### Development

```bash
# Using pixi environment
pixi run -e opencv -- python apps/cv_api/main.py

# Or with fastapi dev
pixi shell -e opencv
fastapi dev apps/cv_api/main.py
```

### Production

```bash
pixi run -e opencv -- python apps/cv_api/main.py
```

## API Endpoints

### POST /compute_similarity

Compute image similarities using CV algorithms.

**Parameters:**
- `image_files`: List of image files to compare (multipart/form-data)
- `algorithm_names`: Sequence of algorithm names (default: `["SIFT"]`)
- `fmt`: Output format - `"arrow_recordbatch"`, `"arrow_tensor"`, `"parquet"`, `"safetensors"`

**Returns:**
Similarity scores with shape `(num_images, num_algorithms, 2)`:
- `[:, :, 0]`: similarities with base image (index 0)
- `[:, :, 1]`: similarities with feature image (index -1)

## Testing

```bash
pixi run -e opencv -- python -m apps.cv_api.test
```
