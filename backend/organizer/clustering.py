import google.generativeai as genai
from PIL import Image
import numpy as np
from sklearn.cluster import DBSCAN
import os

# --- CONSTANTS ---
API_KEY = os.environ.get("GEMINI_API_KEY", "")  # set in your shell, never commit keys
MODEL_NAME = "models/text-embedding-004" # Or multimodal embedding model if available?
# Gemini 2.5 Flash is a generative model. For embeddings, we usually use 'models/embedding-001' or similar.
# However, Gemini 1.5 Pro/Flash supports multimodal input for generation.
# For pure vector embeddings of images, we might need a specific model.
# Google's 'models/embedding-001' is text-only.
# 'models/multimodal-embedding-001' exists?
# Let's check the docs or assume we use the Generative Model to describe the image, then embed the description + text.
# OR, we use the 'embedding-001' for text (filename) and rely on Gemini 2.5 Flash to generate a rich description first.
# Strategy: Image -> Gemini 2.5 Flash -> "Detailed Description" -> Text Embedding Model -> Vector.
# This is safer and uses the powerful 2.5 Flash.

EMBEDDING_MODEL = "models/text-embedding-004"

genai.configure(api_key=API_KEY)

class VectorCluster:
    def __init__(self):
        self.gen_model = genai.GenerativeModel("gemini-2.5-flash")
        
    def get_image_description(self, image_path: str) -> str:
        """
        Uses Gemini 2.5 Flash to get a detailed visual description for embedding.
        """
        try:
            img = Image.open(image_path)
            prompt = "Describe this image in detail (visuals, objects, colors, mood) for semantic clustering. English is fine."
            response = self.gen_model.generate_content([prompt, img])
            return response.text
        except Exception as e:
            print(f"Error describing image {image_path}: {e}")
            return ""

    def get_embedding(self, text: str) -> np.ndarray:
        """
        Generates vector embedding for text.
        """
        if not text:
            return np.zeros(768) # Assuming 768 dim
            
        try:
            result = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=text,
                task_type="clustering",
            )
            return np.array(result['embedding'])
        except Exception as e:
            print(f"Error embedding text: {e}")
            return np.zeros(768)

    def generate_cluster_name(self, file_paths: list[str]) -> str:
        """
        Generates a short Korean topic name for the cluster using Gemini.
        """
        try:
            # Use first 3 images to guess the topic
            sample_files = file_paths[:3]
            descriptions = []
            for fp in sample_files:
                descriptions.append(os.path.basename(fp))
            
            prompt = f"These are filenames from a photo cluster: {', '.join(descriptions)}. Provide a single, short Korean keyword (noun) that best describes them (e.g., 바다, 고양이, 문서, 셀카). Do not use spaces or special characters."
            
            response = self.gen_model.generate_content(prompt)
            return response.text.strip()
        except Exception:
            return "기타"

    def cluster_files(self, file_paths: list[str]) -> dict:
        """
        Clusters files based on semantic similarity.
        Returns: {cluster_id: [file_paths...]}
        cluster_id -1 means noise (unique/outlier).
        """
        embeddings = []
        valid_files = []
        
        print(f"Generating embeddings for {len(file_paths)} files...")
        
        for fp in file_paths:
            # 1. Get Description (Image -> Text)
            desc = self.get_image_description(fp)
            if not desc:
                continue
                
            # 2. Add Filename Context
            filename = os.path.basename(fp)
            combined_text = f"Filename: {filename}. Visuals: {desc}"
            
            # 3. Get Vector
            vec = self.get_embedding(combined_text)
            embeddings.append(vec)
            valid_files.append(fp)
            
        if not embeddings:
            return {}
            
        X = np.array(embeddings)
        
        # DBSCAN Clustering
        clustering = DBSCAN(eps=0.3, min_samples=2, metric='cosine').fit(X)
        
        clusters = {}
        unique_labels = set(clustering.labels_)
        
        final_clusters = {}
        
        for label in unique_labels:
            label = int(label)
            if label == -1:
                continue # Skip noise for now, or group as 'Unsorted'
                
            # Get files for this cluster
            indices = [i for i, x in enumerate(clustering.labels_) if x == label]
            cluster_files = [valid_files[i] for i in indices]
            
            # Generate Name
            topic = self.generate_cluster_name(cluster_files)
            cluster_name = f"그룹_{label:02d}_{topic}"
            
            final_clusters[label] = {
                "name": cluster_name,
                "files": cluster_files
            }
            
        return final_clusters
